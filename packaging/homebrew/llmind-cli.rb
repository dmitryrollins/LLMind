class LlmindCli < Formula
  include Language::Python::Virtualenv

  desc "Embed signed semantic-metadata layers into images, PDFs, and audio files"
  homepage "https://github.com/dmitryrollins/LLMind"
  # Source is the Python sdist uploaded as a release asset on each cli-vX.Y.Z
  # tag (built and uploaded by .github/workflows/release-homebrew.yml).
  # `version` is explicit because `brew update-python-resources` requires it
  # even though brew can infer the same value from the sdist filename.
  url "https://github.com/dmitryrollins/LLMind/releases/download/cli-v0.1.0/llmind_cli-0.1.0.tar.gz"
  version "0.1.0"
  sha256 "REPLACE_WITH_SHA256_OF_RELEASE_TARBALL"
  license "MIT"

  # Tell livecheck to scan git tags with the cli-v prefix.
  livecheck do
    url "https://github.com/dmitryrollins/LLMind.git"
    regex(/^cli[._-]v?(\d+(?:\.\d+)+)$/i)
    strategy :git
  end

  depends_on "libyaml"   # PyYAML
  depends_on "poppler"   # pdf2image (pdftoppm/pdftocairo)
  depends_on "python@3.12"

  uses_from_macos "libxml2"  # lxml (transitive)
  uses_from_macos "libxslt"  # lxml (transitive)

  # Python dependencies — populated by `brew update-python-resources llmind-cli`
  # after each bump. Do not hand-edit; the release workflow regenerates them.

  def install
    # Bundles cloud providers (anthropic, openai, google-genai) so the CLI
    # works out of the box. Users who want local Whisper can run, post-install:
    #   "#{libexec}/bin/pip install faster-whisper"
    virtualenv_install_with_resources
  end

  test do
    assert_match "llmind", shell_output("#{bin}/llmind --help")
    assert_match version.to_s, shell_output("#{bin}/llmind --version 2>&1")
  end
end
