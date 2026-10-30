# Run with: ruby tests/test_main_sonarqube_scan.rb
require 'minitest/autorun'
require 'yaml'
require 'tmpdir'
require 'fileutils'
require 'open3'
require 'json'

class StandaloneSonarTest < Minitest::Test
  ROOT = File.expand_path('..', __dir__)
  WORKFLOW = YAML.load_file(File.join(ROOT, '.github/workflows/main-sonarqube-scan.yml'))
  STEPS = WORKFLOW.fetch('jobs').fetch('analysis').fetch('steps')

  def setup
    @dir = File.realpath(Dir.mktmpdir('standalone-sonar-'))
    @env = {
      'GITHUB_WORKSPACE' => @dir, 'GITHUB_OUTPUT' => "#{@dir}/outputs",
      'GITHUB_STEP_SUMMARY' => "#{@dir}/summary", 'GITHUB_REPOSITORY' => 'test/repo',
      'GITHUB_EVENT_NAME' => 'workflow_dispatch', 'TARGET_BRANCH' => 'main',
      'SCANNER' => 'maven', 'SONAR_TOKEN' => 'test-token', 'SONAR_HOST_URL' => 'https://sonar.example',
      'NOTIFY_TEAMS' => 'true', 'TEAMS_WEBHOOK_URL' => 'https://teams.example/webhook',
      'PREPARATION_SCRIPT' => '', 'GATE_TIMEOUT' => '300', 'COVERAGE_PATHS' => '**/jacoco.xml'
    }
  end

  def teardown
    FileUtils.remove_entry(@dir)
  end

  def step(name)
    STEPS.find { |s| s.fetch('name', '') == name }.fetch('run')
  end

  def execute(script, env = {})
    Open3.capture3(@env.merge(env), 'bash', '-e', '-o', 'pipefail', '-c', script, chdir: @dir)
  end

  def test_input_validation_and_event_guard
    script = step('Validate configuration')
    assert execute(script).last.success?
    [{'SCANNER'=>'unknown'}, {'SONAR_TOKEN'=>''}, {'SONAR_HOST_URL'=>''},
     {'GATE_TIMEOUT'=>'0'}, {'GATE_TIMEOUT'=>'1.5'}, {'COVERAGE_PATHS'=>''},
     {'TEAMS_WEBHOOK_URL'=>''}, {'SCANNER'=>'cli'}, {'GITHUB_EVENT_NAME'=>'pull_request'},
     {'GITHUB_EVENT_NAME'=>'push','GITHUB_REF'=>'refs/heads/feature'}].each do |env|
      refute execute(script, env).last.success?, env.inspect
    end
    assert execute(script, 'SCANNER'=>'cli', 'PREPARATION_SCRIPT'=>'ci/coverage.sh').last.success?
    assert execute(script, 'NOTIFY_TEAMS'=>'false', 'TEAMS_WEBHOOK_URL'=>'').last.success?
    assert execute(script, 'GITHUB_EVENT_NAME'=>'push', 'GITHUB_REF'=>'refs/heads/main').last.success?
  end

  def test_source_sha_and_preparation_paths_use_the_checked_out_branch
    commands = [
      ['git', 'init', '-b', 'main'],
      ['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-m', 'fixture'],
      ['git', 'update-ref', 'refs/remotes/origin/main', 'HEAD']
    ]
    commands.each do |args|
      _out, err, status = Open3.capture3(*args, chdir: @dir)
      assert status.success?, err
    end
    FileUtils.mkdir_p("#{@dir}/app/ci")
    File.write("#{@dir}/app/ci/prepare.sh", 'true')
    script = step('Record source and validate paths')
    _out, err, status = execute(script, 'PROJECT_DIR'=>'app', 'PREPARATION_SCRIPT'=>'ci/prepare.sh')
    assert status.success?, err
    sha, = Open3.capture3('git', 'rev-parse', 'HEAD', chdir: @dir)
    assert_includes File.read("#{@dir}/outputs"), "sha=#{sha.strip}"
    refute execute(script, 'PROJECT_DIR'=>'..').last.success?
    File.symlink('/tmp', "#{@dir}/app/outside")
    refute execute(script, 'PROJECT_DIR'=>'app', 'PREPARATION_SCRIPT'=>'outside/missing.sh').last.success?
    refute execute(script, 'PROJECT_DIR'=>'app', 'TARGET_BRANCH'=>'missing').last.success?
  end

  def test_coverage_must_be_regenerated_and_every_pattern_must_match
    FileUtils.mkdir_p("#{@dir}/module/target/site/jacoco")
    path = "#{@dir}/module/target/site/jacoco/jacoco.xml"
    File.write(path, '<coverage/>')
    assert execute(step('Remove pre-existing coverage reports')).last.success?
    refute File.exist?(path)
    refute execute(step('Require fresh coverage reports')).last.success?
    File.write(path, '<coverage/>')
    assert execute(step('Require fresh coverage reports')).last.success?
    assert_includes File.read("#{@dir}/outputs"), 'sonar-paths=**/jacoco.xml'
    refute execute(step('Require fresh coverage reports'), 'COVERAGE_PATHS'=>"**/jacoco.xml\nmissing.xml").last.success?
    File.write(path, '')
    refute execute(step('Require fresh coverage reports')).last.success?
    refute execute(step('Remove pre-existing coverage reports'), 'COVERAGE_PATHS'=>'../outside.xml').last.success?
  end

  def test_maven_command_does_not_evaluate_shell_text_or_deploy
    bin = "#{@dir}/bin"
    FileUtils.mkdir_p(bin)
    File.write("#{bin}/mvn", "#!/bin/bash\nprintf '%s\\n' \"$@\" > \"$GITHUB_WORKSPACE/maven-args\"\n")
    File.chmod(0755, "#{bin}/mvn")
    _out, err, status = execute(step('Build Maven reactor and generate coverage'),
      'PATH'=>"#{bin}:#{ENV.fetch('PATH')}", 'MAVEN_PROFILES'=>'coverage,docker',
      'MAVEN_ARGS'=>'-Dtest.maxForks=1 $(touch injected)')
    assert status.success?, err
    args = File.readlines("#{@dir}/maven-args", chomp: true)
    assert_includes args, 'clean'
    assert_includes args, 'install'
    assert_includes args, '-Pcoverage,docker'
    refute_includes args, 'deploy'
    refute File.exist?("#{@dir}/injected")
  end

  def test_metadata_survives_gate_failure_and_monorepo_directory
    FileUtils.mkdir_p("#{@dir}/.scannerwork")
    File.write("#{@dir}/.scannerwork/report-task.txt", "dashboardUrl=https://sonar.example/dashboard?id=test\n")
    assert execute(step('Capture analysis links even after a failed gate'), 'MAVEN_SCAN_OUTCOME'=>'failure').last.success?
    assert_includes File.read("#{@dir}/outputs"), 'failure-stage=analysis/quality gate'
    assert_includes File.read("#{@dir}/outputs"), 'dashboard-url=https://sonar.example/dashboard?id=test'
    action = YAML.load_file(File.join(ROOT, '.github/actions/mvn-sast-scanning/action.yaml'))
    assert_equal '.', action.fetch('inputs').fetch('working-directory').fetch('default')
    action.fetch('runs').fetch('steps').select { |s| s['run'] }.each do |s|
      assert_equal '${{ inputs.working-directory }}', s['working-directory']
    end
  end

  def test_teams_payload_escapes_values_and_delivery_errors_fail
    script = WORKFLOW.fetch('jobs').fetch('notify-teams').fetch('steps').first.fetch('run')
    bin = "#{@dir}/bin"
    FileUtils.mkdir_p(bin)
    File.write("#{bin}/curl", "#!/bin/bash\nexit ${CURL_STATUS:-0}\n")
    File.chmod(0755, "#{bin}/curl")
    env = {'PATH'=>"#{bin}:#{ENV.fetch('PATH')}", 'RUNNER_TEMP'=>@dir,
      'REPOSITORY'=>"org/quote\"repo", 'SOURCE_SHA'=>'abc123', 'SCANNER'=>'cli',
      'RUN_URL'=>'https://github.example/run/1', 'DASHBOARD_URL'=>'https://sonar.example/dashboard'}
    assert execute(script, env).last.success?
    payload = JSON.parse(File.read("#{@dir}/sonarqube-teams.json"))
    assert_equal 'message', payload.fetch('type')
    assert_nil payload.fetch('attachments').first.fetch('contentUrl')
    card = payload.fetch('attachments').first.fetch('content')
    assert_equal "org/quote\"repo", card.fetch('body').last.fetch('facts').first.fetch('value')
    assert_equal 2, card.fetch('actions').length
    assert execute(script, env.merge('DASHBOARD_URL'=>'')).last.success?
    card = JSON.parse(File.read("#{@dir}/sonarqube-teams.json")).fetch('attachments').first.fetch('content')
    assert_equal 1, card.fetch('actions').length
    refute execute(script, env.merge('CURL_STATUS'=>'22')).last.success?
    refute execute(script, env.merge('TEAMS_WEBHOOK_URL'=>'')).last.success?
    assert_includes WORKFLOW.fetch('jobs').fetch('notify-teams').fetch('if'), "needs.analysis.result == 'failure'"
  end
end
