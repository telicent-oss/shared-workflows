#!/usr/bin/env bash

ERRORS=0
function abort() {
    echo "  FAIL: $*" 1>&2
    if [ -z "${CONTINUE_ON_ERROR}" ]; then
      exit 1
    else
      ERRORS=$(( ${ERRORS} + 1))
    fi
}

function verified() {
    echo "  PASS: $*"
}

DIRECTORY=$1
pushd "${DIRECTORY}" || abort "Invalid directory (${DIRECTORY}) supplied"
if [ ${ERRORS} -gt 0 ]; then
  exit 1
fi

if [ ! -f pom.xml ]; then
  abort "Not a Maven project, no top level pom.xml in ${DIRECTORY}"
  exit 1
fi

function getMavenProperty() {
    local POM=$1
    local PROPERTY=$2
    mvn -q -f "${POM}" -Dexec.executable=echo -Dexec.args="\${${PROPERTY}}" --non-recursive exec:exec
}

function hasMavenProperty() {
    local POM=$1
    local PROPERTY=$2
    local EXPECTED=$3
    local VALUE=$(getMavenProperty "${POM}" "${PROPERTY}")
    if [ -z "${VALUE}" ]; then
      abort "POM file ${POM} does not have the required Maven Property ${PROPERTY} set"
      return
    else
       local TRIMMED_VALUE=$(echo "${VALUE}" | tr -d ' ')
       if [ -z "${TRIMMED_VALUE}" ]; then
         abort "POM file ${POM} does not have the required Maven Property ${PROPERTY} set"
         return
       fi
    fi
    if [ -n "${EXPECTED}" ]; then
      if [ "${VALUE}" != "${EXPECTED}" ]; then
        abort "POM file ${POM} does not have the expected value for Maven Property ${PROPERTY} set, expected ${EXPECTED} but found ${VALUE}"
        return
      fi
    fi

    verified "Verified POM file ${POM} has required Maven Property ${PROPERTY} set as:"
    verified "${VALUE}"
}

function hasMavenConfiguration() {
    local POM=$1
    local XPATH=$2
    local DESCRIPTION=$3
    local EXPECTED=$4

    local VALUE=$(xidel -se "${XPATH}" "/tmp/pom.xml")

    if [ -z "${VALUE}" ]; then
      abort "POM file ${POM} does not have ${DESCRIPTION}"
      return
    fi
    if [ -n "${EXPECTED}" ]; then
      if [ "${EXPECTED}" != "${VALUE}" ]; then
        abort "POM file ${POM} does not have the expected value for ${DESCRIPTION}, expected ${EXPECTED} but found ${VALUE}"
        return
      fi
    fi
    
    verified "Verified POM file ${POM} has ${DESCRIPTION}"
}

function hasMavenArtifact() {
    local POM=$1
    local BUILD_DIR="$(dirname ${POM})/target/"
    local FILE=$2
    local DESCRIPTION=$2

    if [ ! -f "${BUILD_DIR}${FILE}" ]; then
      abort "POM file ${POM} does not produce a ${DESCRIPTION} in its target/ directory"
      return
    else
      verified "Verified POM file ${POM} produces a ${DESCRIPTION}"
    fi
}

echo "Quick Building the Maven Project..."
mvn clean install -DskipTests >/dev/null 2>&1 || abort "Maven Build Failed"
echo "Maven Build completed"
echo "---"
echo

for POM in $(find . -name pom.xml); do
  echo "Testing POM file ${POM}..."
  pwd

  # Check for Basic Metadata
  echo "Basic Metadata Checks..."
  hasMavenProperty "${POM}" "project.version"
  hasMavenProperty "${POM}" "project.name"
  hasMavenProperty "${POM}" "project.description"
  hasMavenProperty "${POM}" "project.url"

  echo "Advanced Metadata Checks..."
  rm /tmp/pom.xml
  mvn -f "${POM}" help:effective-pom -Doutput=/tmp/pom.xml >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    abort "POM file ${POM} could not have an effective POM file generated for it"
    continue
  fi

  # Check for Licenses
  hasMavenConfiguration "${POM}" "//project[last()]/licenses[1]/license/url" "<licenses> section"

  # Check for Developers
  hasMavenConfiguration "${POM}" "//project[last()]/developers[1]/developer/email" "<developers> section" "opensource@telicent.io"

  # Check for SCM Information
  hasMavenConfiguration "${POM}" "//project[last()]/scm/url" "<scm> section"

  # Check for Distribution Management
  hasMavenConfiguration "${POM}" "//project[last()]/distributionManagement/repository/url" "<distributionManagement> section" "https://s01.oss.sonatype.org/service/local/staging/deploy/maven2/"

  # Check aritifacts
  echo "Artifact Checks..."
  PACKAGING=$(getMavenProperty "${POM}" "project.packaging")
  ARTIFACT_ID=$(getMavenProperty "${POM}" "project.artifactId")
  VERSION=$(getMavenProperty "${POM}" "project.version")
  echo "POM file ${POM} has packaging type ${PACKAGING}"

  if [ "${PACKAGING}" != "pom" ]; then
    hasMavenArtifact "${POM}" "${ARTIFACT_ID}-${VERSION}.jar" "JAR File"
    hasMavenArtifact "${POM}" "${ARTIFACT_ID}-${VERSION}-sources.jar" "Sources JAR"
    hasMavenArtifact "${POM}" "${ARTIFACT_ID}-${VERSION}-javadoc.jar" "Javadoc JAR"
  fi
  hasMavenArtifact "${POM}" "${ARTIFACT_ID}-${VERSION}-bom.json" "JSON SBOM"
  hasMavenArtifact "${POM}" "${ARTIFACT_ID}-${VERSION}-bom.xml" "XML SBOM"

  # Verifying Signatures are present
  echo "Signature Checks..."
  for ARTIFACT in $(find "$(dirname ${POM})/target" -type f -not -name "*.asc" -d 1); do
    EXTENSION=${ARTIFACT##*.}
    case ${EXTENSION} in
      "txt"|"log")
        continue
        ;;
      *)
        if [ ! -f "${ARTIFACT}.asc" ]; then
          abort "POM file ${POM} produces artifact ${ARTIFACT} that does not have a corresponding digital signature file"
        else
          verified "Verified POM file ${POM} generates digital signature for artifact ${ARTIFACT}"
        fi
        ;;
    esac
  done

  echo "---"
  echo
done

if [ ${ERRORS} -gt 0 ]; then
  echo "Maven Project in ${DIRECTORY} had various errors, please see above output for details"
  exit 1
else
  echo "Maven Project in ${DIRECTORY} appears ready for Maven Central"
fi
