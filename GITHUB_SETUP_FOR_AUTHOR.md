# GitHub setup for the author

The Codex GitHub connector available in this environment can write files to an
existing accessible repository, but it does not expose a new-repository creation
tool. Create the repository once in the GitHub web UI, then the prepared package
can be uploaded.

## Create the repository

1. Open https://github.com/new while signed in as `kanair-gif`.
2. Repository name: `gmw-neuron-review-code`.
3. Visibility: `Public`.
4. Do not add a README, license, or gitignore in the web form if you want this
   prepared folder to become the initial contents without conflicts.
5. Create the repository.

## Upload contents

After the public repository exists, either:

- tell Codex the repository URL so it can try to upload text files through the
  GitHub connector, or
- upload the prepared ZIP manually through GitHub's web interface.

Because the repository must provide anonymous reviewer access, confirm in a
private/incognito browser window that the final URL opens without login.

## Current intended URL

```text
https://github.com/kanair-gif/gmw-neuron-review-code
```

