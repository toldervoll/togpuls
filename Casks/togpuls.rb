cask "togpuls" do
  version "0.1.3"
  sha256 "f9e8e5269feb24d1cf8786b3dee732b20679957dd70d409d679d840f96bf225d"

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
