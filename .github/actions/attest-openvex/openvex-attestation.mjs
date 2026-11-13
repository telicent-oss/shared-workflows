// Grype and Trivy only apply an attested statement whose product is the scanned
// image digest and whose subcomponent is the flagged package, hence the re-scoping.

// Trivy writes distro=redhat-9.8, Syft distro=rhel-9.8, and older statements
// carry the rpm epoch in the version; name@version is what both agree on.
export function normalisePurl(purl) {
  return purl.replace(/#.*$/, "").replace(/\?.*$/, "").replace(/@\d+:/, "@");
}

export function imageProductId(repository, digest) {
  const name = repository.split("/").at(-1);
  return `pkg:oci/${name}@${encodeURIComponent(digest)}?repository_url=${encodeURIComponent(repository)}`;
}

export function buildAttestation({
  documents,
  purls,
  repository,
  digests,
  timestamp,
}) {
  const present = new Set(purls.map(normalisePurl));
  const products = digests.map((digest) => imageProductId(repository, digest));

  // Re-scoped statements share their products, and merge-vex-action dedupes on
  // vulnerability + products, so same-CVE statements must be combined here.
  const merged = new Map();
  for (const statement of documents.flatMap((doc) => doc.statements ?? [])) {
    const packages = (statement.products ?? [])
      .flatMap((product) => [
        product["@id"],
        ...(product.subcomponents ?? []).map((sub) => sub["@id"]),
      ])
      .filter(Boolean)
      .map(normalisePurl)
      .filter((purl) => present.has(purl));
    if (packages.length === 0) continue;
    const key = `${statement.vulnerability?.name}|${statement.status}`;
    const entry = merged.get(key);
    if (!entry) {
      merged.set(key, {
        statement,
        packages: new Set(packages),
        impacts: new Set([statement.impact_statement].filter(Boolean)),
      });
    } else {
      packages.forEach((purl) => entry.packages.add(purl));
      if (statement.impact_statement) entry.impacts.add(statement.impact_statement);
    }
  }

  const statements = [...merged.values()].map(({ statement, packages, impacts }) => ({
    ...statement,
    ...(impacts.size > 0 && { impact_statement: [...impacts].join("\n\n") }),
    products: products.map((id) => ({
      "@id": id,
      subcomponents: [...packages].sort().map((purl) => ({ "@id": purl })),
    })),
  }));

  return {
    "@context": "https://openvex.dev/ns/v0.2.0",
    "@id": `https://telicent.io/vex/${repository.split("/").at(-1)}/${digests[0]}`,
    author: "Telicent Ltd",
    timestamp,
    version: 1,
    statements,
  };
}

// Runner: node openvex-attestation.mjs <vex-file> <purls-file> <repository> <digest>...
if (import.meta.url === `file://${process.argv[1]}`) {
  const { readFileSync } = await import("node:fs");
  const [vexFile, purlsFile, repository, ...digests] = process.argv.slice(2);
  if (!vexFile || !purlsFile || !repository || digests.length === 0) {
    console.error(
      "Usage: openvex-attestation.mjs <vex-file> <purls-file> <repository> <digest>...",
    );
    process.exit(1);
  }
  const documents = [JSON.parse(readFileSync(vexFile, "utf8"))];
  const purls = readFileSync(purlsFile, "utf8").split("\n").filter(Boolean);
  const attestation = buildAttestation({
    documents,
    purls,
    repository,
    digests,
    timestamp: new Date().toISOString(),
  });
  console.log(JSON.stringify(attestation, null, 2));
}
