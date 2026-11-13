import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildAttestation,
  imageProductId,
  normalisePurl,
} from "./openvex-attestation.mjs";

const REPOSITORY = "quay.io/telicent/telicent-search";
const INDEX = "sha256:aaaa";
const AMD64 = "sha256:bbbb";

const statement = (name, ...ids) => ({
  vulnerability: { name },
  products: ids.map((id) => ({ "@id": id })),
  status: "not_affected",
  justification: "vulnerable_code_not_in_execute_path",
  impact_statement: `${name} is not reachable`,
});

const build = (statements, purls) =>
  buildAttestation({
    documents: [{ statements }],
    purls,
    repository: REPOSITORY,
    digests: [INDEX, AMD64],
    timestamp: "2026-10-29T00:00:00.000Z",
  });

test("Trivy and Syft PURLs for the same rpm normalise to the same identifier", () => {
  const trivy =
    "pkg:rpm/redhat/tar@1.34-13.el9_8?arch=x86_64&distro=redhat-9.8&epoch=2";
  const syft =
    "pkg:rpm/redhat/tar@1.34-13.el9_8?arch=x86_64&distro=rhel-9.8&epoch=2&upstream=tar-1.34-13.el9_8.src.rpm";
  assert.equal(normalisePurl(trivy), "pkg:rpm/redhat/tar@1.34-13.el9_8");
  assert.equal(normalisePurl(syft), normalisePurl(trivy));
});

test("an epoch written into the version is dropped", () => {
  assert.equal(
    normalisePurl("pkg:rpm/redhat/tar@2:1.34-7.el9?distro=redhat-9.6"),
    "pkg:rpm/redhat/tar@1.34-7.el9",
  );
});

test("the image product is a pkg:oci PURL with an encoded digest and repository", () => {
  assert.equal(
    imageProductId(REPOSITORY, INDEX),
    "pkg:oci/telicent-search@sha256%3Aaaaa?repository_url=quay.io%2Ftelicent%2Ftelicent-search",
  );
});

test("a statement for a package in the image is re-scoped to every image digest", () => {
  const doc = build(
    [
      statement(
        "CVE-1",
        "pkg:rpm/redhat/gnupg2@2.3.3-5.el9_7?arch=x86_64&distro=redhat-9.8",
      ),
    ],
    ["pkg:rpm/redhat/gnupg2@2.3.3-5.el9_7?arch=x86_64&distro=rhel-9.8"],
  );
  assert.equal(doc.statements.length, 1);
  const [index, amd64, ...rest] = doc.statements[0].products;
  assert.deepEqual(
    [index["@id"], amd64["@id"]],
    [imageProductId(REPOSITORY, INDEX), imageProductId(REPOSITORY, AMD64)],
  );
  for (const product of [index, amd64]) {
    assert.deepEqual(product.subcomponents, [
      { "@id": "pkg:rpm/redhat/gnupg2@2.3.3-5.el9_7" },
    ]);
  }
  assert.deepEqual(rest, [{ "@id": "pkg:rpm/redhat/gnupg2@2.3.3-5.el9_7" }]);
  assert.equal(doc.statements[0].impact_statement, "CVE-1 is not reachable");
});

test("statements for packages or versions not in the image are left out", () => {
  const doc = build(
    [
      statement("CVE-1", "pkg:rpm/redhat/wget@1.21.1-8.el9_4"),
      statement("CVE-2", "pkg:maven/org.lz4/lz4-java@1.8.0"),
    ],
    ["pkg:rpm/redhat/wget@1.21.1-11.el9_8?arch=x86_64"],
  );
  assert.deepEqual(doc.statements, []);
});

test("only the matching versions of a multi-version statement become subcomponents", () => {
  const doc = build(
    [
      statement(
        "CVE-1",
        "pkg:rpm/redhat/libarchive@3.5.3-6.el9_6?arch=x86_64",
        "pkg:rpm/redhat/libarchive@3.5.3-11.el9_8?arch=x86_64",
        "pkg:rpm/redhat/libarchive@3.5.3-11.el9_8?arch=aarch64",
      ),
    ],
    ["pkg:rpm/redhat/libarchive@3.5.3-11.el9_8?arch=x86_64&distro=rhel-9.8"],
  );
  assert.deepEqual(doc.statements[0].products[0].subcomponents, [
    { "@id": "pkg:rpm/redhat/libarchive@3.5.3-11.el9_8" },
  ]);
});

test("statements for the same vulnerability and status are combined into one", () => {
  const doc = build(
    [
      statement("GHSA-1", "pkg:npm/a@1.0.0"),
      { ...statement("GHSA-1", "pkg:npm/b@2.0.0"), impact_statement: "b is unused" },
      statement("GHSA-1", "pkg:npm/c@3.0.0"),
    ],
    ["pkg:npm/a@1.0.0", "pkg:npm/b@2.0.0"],
  );
  assert.equal(doc.statements.length, 1);
  assert.deepEqual(doc.statements[0].products[0].subcomponents, [
    { "@id": "pkg:npm/a@1.0.0" },
    { "@id": "pkg:npm/b@2.0.0" },
  ]);
  assert.equal(
    doc.statements[0].impact_statement,
    "GHSA-1 is not reachable\n\nb is unused",
  );
});

test("statements for the same vulnerability with different statuses stay separate", () => {
  const doc = build(
    [
      statement("CVE-1", "pkg:npm/a@1.0.0"),
      { ...statement("CVE-1", "pkg:npm/b@2.0.0"), status: "fixed" },
    ],
    ["pkg:npm/a@1.0.0", "pkg:npm/b@2.0.0"],
  );
  assert.deepEqual(
    doc.statements.map((s) => s.status),
    ["not_affected", "fixed"],
  );
});

test("a package bundled inside another is matched through its subcomponents", () => {
  const doc = build(
    [
      {
        ...statement("GHSA-1"),
        products: [
          {
            "@id":
              "pkg:maven/io.opentelemetry.javaagent/opentelemetry-javaagent@1.33.6",
            subcomponents: [
              {
                "@id":
                  "pkg:maven/com.fasterxml.jackson.core/jackson-core@2.16.1",
              },
            ],
          },
        ],
      },
    ],
    ["pkg:maven/com.fasterxml.jackson.core/jackson-core@2.16.1"],
  );
  assert.deepEqual(doc.statements[0].products[0].subcomponents, [
    { "@id": "pkg:maven/com.fasterxml.jackson.core/jackson-core@2.16.1" },
  ]);
});
