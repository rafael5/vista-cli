# Homebrew formula for vista-cli.
#
# Developer install (no Python or pip required of the user):
#
#     brew tap rafael5/vista https://github.com/rafael5/vista-cli
#     brew install vista
#
# Homebrew handles the Python interpreter via the `python@3.12`
# dependency — the user never sees pip or a venv.
#
# After install, run `vista init` to fetch the snapshot data bundle.
#
# To update this formula on a release:
#   1. Bump `url` to the new tag's source archive on GitHub.
#   2. Recompute `sha256`:
#        curl -L <url> | shasum -a 256
#   3. Bump `version`.
#
# `brew livecheck` can automate the URL bump if pointed at the
# Releases atom feed.

class Vista < Formula
  include Language::Python::Virtualenv

  desc "Joined VistA code + documentation queries (vista-cli)"
  homepage "https://github.com/rafael5/vista-cli"
  url "https://github.com/rafael5/vista-cli/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_TAG_ARCHIVE_SHA256_ON_RELEASE"
  license "MIT"

  depends_on "python@3.12"

  # The single Python runtime dependency. Sourced from PyPI as a
  # Homebrew resource — this is the standard pattern for declaring
  # third-party Python deps in a formula and is not a vista-cli
  # distribution channel.
  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "ca9853ad459e787e2192211578cc907e7594e294c7ccc834310722b41b9ca6de"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    # Smoke-test: --version exits 0 and prints the right name.
    assert_match "vista", shell_output("#{bin}/vista --version")
    # `vista doctor` exits non-zero only when both stores are missing,
    # which is fine here — we're just checking that the CLI is wired
    # up. The output should always include the well-known label.
    output = shell_output("#{bin}/vista doctor 2>&1", 0..1)
    assert_match "code-model", output
  end
end
