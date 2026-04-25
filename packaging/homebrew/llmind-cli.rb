class LlmindCli < Formula
  include Language::Python::Virtualenv

  desc "Embed signed semantic-metadata layers into images, PDFs, and audio files"
  homepage "https://github.com/dmitryrollins/LLMind"
  # Source tarball is the GitHub release for the `cli-vX.Y.Z` tag.
  # Update `url`, `sha256`, and `version` together when bumping.
  url "https://github.com/dmitryrollins/LLMind/archive/refs/tags/cli-v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_OF_RELEASE_TARBALL"
  license "MIT"
  version "0.1.0"

  # The cli-v* tag prefix means Homebrew can't auto-detect the version from
  # the URL. Pin it via `version` above and tell livecheck to strip the prefix.
  livecheck do
    url :stable
    regex(/^cli[._-]v?(\d+(?:\.\d+)+)$/i)
    strategy :git
  end

  depends_on "poppler" # pdf2image runtime dependency (pdftoppm/pdftocairo)
  depends_on "python@3.12"

  # Python dependencies — populated by `brew update-python-resources llmind-cli`
  # after each bump. Do not hand-edit; the release workflow regenerates them.

  def install
    # The release tarball is the full LLMind monorepo; the CLI lives in
    # `llmind-cli/`. cd into it so virtualenv_install_with_resources picks up
    # the right pyproject.toml.
    cd "llmind-cli" do
      # Install with bundled cloud providers so the CLI works out of the box.
      # Users who want local Whisper can run, after install:
      #   "#{libexec}/bin/pip install faster-whisper"
      virtualenv_install_with_resources
    end
  end

  test do
    assert_match "llmind", shell_output("#{bin}/llmind --help")
    assert_match version.to_s, shell_output("#{bin}/llmind --version 2>&1", 0)
  end
end
