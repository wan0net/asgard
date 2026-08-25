// SPDX-License-Identifier: BSD-3-Clause

const replacements: ReadonlyArray<{
  path: string;
  before: string;
  after: string;
}> = [
  {
    path: "apps/host-selfhost/executor.config.ts",
    before: 'import { encryptedSecretsPlugin } from "@executor-js/plugin-encrypted-secrets";\n',
    after:
      'import { encryptedSecretsPlugin } from "@executor-js/plugin-encrypted-secrets";\n' +
      'import { onepasswordHttpPlugin } from "@executor-js/plugin-onepassword/api";\n',
  },
  {
    path: "apps/host-selfhost/executor.config.ts",
    before:
      "      encryptedSecretsPlugin({ key: resolveSecretKey() }),\n" +
      "    ] as const,\n",
    after:
      "      encryptedSecretsPlugin({ key: resolveSecretKey() }),\n" +
      "      // External, read-only provider. The host supplies the service-account\n" +
      "      // credential at runtime; it is not persisted in plugin storage.\n" +
      "      onepasswordHttpPlugin(),\n" +
      "    ] as const,\n",
  },
  {
    path: "apps/host-selfhost/package.json",
    before: '    "@executor-js/plugin-mcp": "workspace:*",\n',
    after:
      '    "@executor-js/plugin-mcp": "workspace:*",\n' +
      '    "@executor-js/plugin-onepassword": "workspace:*",\n',
  },
  {
    path: "packages/plugins/onepassword/src/sdk/plugin.ts",
    before: 'const PROVIDER_KEY = ProviderKey.make("onepassword");\n',
    after:
      'const PROVIDER_KEY = ProviderKey.make("onepassword");\n' +
      'const RUNTIME_SERVICE_ACCOUNT_TOKEN = "__EXECUTOR_RUNTIME_1PASSWORD_TOKEN__";\n',
  },
  {
    path: "packages/plugins/onepassword/src/sdk/plugin.ts",
    before: "          auth: config.auth,\n",
    after:
      "          auth:\n" +
      '            config.auth.kind === "service-account"\n' +
      '              ? { kind: "service-account", token: RUNTIME_SERVICE_ACCOUNT_TOKEN }\n' +
      "              : config.auth,\n",
  },
  {
    path: "packages/plugins/onepassword/src/sdk/plugin.ts",
    before: '    : { kind: "service-account", token: auth.token };\n',
    after:
      "    : {\n" +
      '        kind: "service-account",\n' +
      "        token:\n" +
      "          auth.token === RUNTIME_SERVICE_ACCOUNT_TOKEN\n" +
      '            ? (process.env.OP_SERVICE_ACCOUNT_TOKEN ?? "")\n' +
      "            : auth.token,\n" +
      "      };\n",
  },
];

for (const replacement of replacements) {
  const source = await Bun.file(replacement.path).text();
  const occurrences = source.split(replacement.before).length - 1;
  if (occurrences !== 1) {
    throw new Error(
      `onepassword self-host patch expected one target in ${replacement.path}, found ${occurrences}`,
    );
  }
  await Bun.write(replacement.path, source.replace(replacement.before, replacement.after));
}

const plugin = await Bun.file("packages/plugins/onepassword/src/sdk/plugin.ts").text();
if (!plugin.includes("RUNTIME_SERVICE_ACCOUNT_TOKEN")) {
  throw new Error("onepassword runtime-token hardening was not applied");
}
