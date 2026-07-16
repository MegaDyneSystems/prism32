class Prism32 < Formula
  desc "Self-extending polymorphic AI super-agent"
  homepage "https://github.com/MegaDyneSystems/prism32"
  url "https://github.com/MegaDyneSystems/prism32/raw/2152bb1c78ee31a106cab6c46be613186ebfd583/prism32.py"
  sha256 "e4da6c8be6ef065f2b44f801d9cb58c90428c96da47fb17d36b2b6d83c03e167"
  version "6.9.0"
  license "Apache-2.0"

  depends_on "python@3.12"

  def install
    libexec.install "prism32.py"
    (bin/"prism32").write <<~EOS
      #!/bin/bash
      exec "#{Formula["python@3.12"].opt_bin}/python3" "#{libexec}/prism32.py" "$@"
    EOS
    chmod 0755, bin/"prism32"
  end

  test do
    system bin/"prism32", "--version"
  end
end
