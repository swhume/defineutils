# Signing the Windows executables

The `sign-windows` job in `.github/workflows/executables.yml` signs the Windows build with
[Azure Artifact Signing](https://learn.microsoft.com/azure/artifact-signing/). It stays off until the setup below is
done; until then every build, including a release, is unsigned. The macOS build is not signed yet.

## What is signed, and when

- **When:** on a `v*` tag, or on a manual run with "sign" ticked, once the `ARTIFACT_SIGNING_ACCOUNT` repository
  variable is set. Pushes to a branch build unsigned.
- **What:** each file without a signature: the six commands and lxml's seven modules (13 files today; see
  `windows_signing.ps1 -Action List`). Python's DLLs and the Microsoft runtime keep the signatures their publishers
  gave them.
- **Timestamp:** every signature is timestamped. Artifact Signing certificates last three days, and the timestamp is
  what keeps a signature valid after that.
- **The build that is signed** is the zip the build job built and tested. The job signs it, rezips it and runs the
  whole test suite against the signed executables, and a tag's release waits for it. On a signing run, the only
  Windows zip uploaded under the zip's own name is the signed one.
- **Every Windows build** also signs a copy with a throwaway certificate and runs the commands from it. So a change that
  breaks signed executables (a PyInstaller upgrade, say) fails an ordinary push rather than a release.
- **Cost:** the Basic plan is about US$9.99 a month for 5,000 signatures; a signing run uses 13.

## One-time setup

### Azure

Identity validation takes 1 to 20 business days. These steps follow Microsoft's
[quickstart](https://learn.microsoft.com/azure/artifact-signing/quickstart), which has the details.

1. **A paid Azure subscription:** free, trial and sponsored ones are refused. For individual validation, the
   subscription's billing account must be of type Individual, with your legal name and address as they appear on your
   government ID. That name is the publisher Windows shows.
2. **Register the provider:** in the subscription's Resource providers, register `Microsoft.CodeSigning`.
3. **Create an Artifact Signing account** on the Basic plan. Note the endpoint for its region, for example
   `https://eus.codesigning.azure.net` for East US (the quickstart lists them).
4. **Validate your identity:** assign yourself the **Artifact Signing Identity Verifier** role on the account, then
   create the identity validation (Individual or Organization, Public) in the portal. Individuals must be in the USA or
   Canada.
5. **Create a certificate profile** of type **Public Trust**, using that identity validation.
6. **Create an app registration in Microsoft Entra ID** (App registrations > New registration), for example
   `defineutils-signing`. Under Certificates & secrets > Federated credentials, add one:
   - scenario: GitHub Actions deploying Azure resources;
   - organization `swhume`, repository `defineutils`;
   - entity type **Environment**, environment `signing`.

   Use an environment, not a tag: Entra matches tag names exactly, so a tag credential would only work for one
   release.
7. **Give the app the signing role:** on the certificate profile, under Access control (IAM), assign the
   **Artifact Signing Certificate Profile Signer** role to the app registration.

### GitHub (the repository's Settings)

1. **Create the `signing` environment** (Environments > New environment, named `signing`). Under "Deployment branches
   and tags", choose selected branches and tags, then add the tag rule `v*` and the branch you will try a manual run
   from (e.g. `main`). Optionally, add yourself as a required reviewer so each signing waits for your approval.
2. **Add the `signing` environment's secrets:**
   - `AZURE_CLIENT_ID`: the app registration's Application (client) ID;
   - `AZURE_TENANT_ID`;
   - `AZURE_SUBSCRIPTION_ID`.
3. **Add the repository variables** (Secrets and variables > Actions > Variables):
   - `ARTIFACT_SIGNING_ENDPOINT`;
   - `ARTIFACT_SIGNING_PROFILE`: the certificate profile's name;
   - `ARTIFACT_SIGNING_ACCOUNT`: the account's name. Add it last, since setting it turns signing on.

### Try it before a release

1. Run the workflow by hand (Actions > executables > Run workflow) from a branch the `signing` environment allows, with
   "sign" ticked.
2. Check the sign-windows job's log. "List the files to sign" names the files, and "Check the signatures" shows each
   one as Valid and timestamped, with your name as the signer.
3. Download the `defineutils-<version>-windows-x64.zip` artifact. On Windows, open the Properties of `definehtml.exe`:
   the Digital Signatures tab shows your name.

## After the first signed release

- **Update the warnings.** The Windows instructions in README.md ("Downloading the commands") and in
  `packaging/README.txt` still say the commands are not code-signed. Change them before tagging, because README.txt is
  copied into the bundle when it is built. Signed commands can still get a SmartScreen warning until a release builds
  up reputation.
- **Tell corporate IT how to allowlist.** The publisher Windows shows is the validated name. The certificate behind it
  is reissued every few days, so allowlist the publisher rather than one certificate's thumbprint.

## When signing fails

- **A 403 from the signing step:** check the role assignment, that the identity validation is Completed, that the
  certificate profile is active, and that `ARTIFACT_SIGNING_ENDPOINT` is the account's own region (Microsoft's
  [FAQ](https://learn.microsoft.com/azure/artifact-signing/faq) lists more).
- **Retrying a tag:** once the problem is fixed in Azure or the repository settings, re-run the failed jobs; the release
  job follows.
- **Releasing unsigned:** delete the `ARTIFACT_SIGNING_ACCOUNT` variable to switch signing off; the next tag build is
  unsigned.
