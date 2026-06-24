cask "togpuls" do
  version "0.1.0"
  sha256 "47df1f0e8878f0828c6ab4b484c3f44908ae9441f660994a47aac427ff49a9aa"

  url "https://github.com/kengu/togpuls/releases/download/macos-v#{version}/Togpuls-#{version}.dmg"
  name "Togpuls"
  desc "Menylinje-app for togavganger fra Entur"
  homepage "https://github.com/kengu/togpuls"

  # Følg macos-v* tagger på dette repoet — strategy: github_latest håndterer
  # det implisitt via siste release.
  livecheck do
    url :url
    strategy :github_latest
  end

  app "Togpuls.app"

  # Appen er ad-hoc-signert, ikke notarisert. Fjerner quarantine så
  # Gatekeeper slipper førstegangslansering uten dialog.
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", "#{appdir}/Togpuls.app"],
                   sudo: false
  end

  zap trash: [
    "~/Library/Preferences/no.kengu.togpuls.menubar.plist",
    "~/Library/Saved Application State/no.kengu.togpuls.menubar.savedState",
    "~/Library/Caches/no.kengu.togpuls.menubar",
  ]
end
