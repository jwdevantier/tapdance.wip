{
  description = "python development flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    vfn = {
      url = "github:SamsungDS/libvfn";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, vfn }:
    let
      allSystems = [
        "x86_64-linux" # AMD/Intel Linux
        "x86_64-darwin" # AMD/Intel macOS
        "aarch64-linux" # ARM Linux
        "aarch64-darwin" # ARM macOS
      ];

      forAllSystems = fn:
        nixpkgs.lib.genAttrs allSystems
        (system: fn {
          pkgs = import nixpkgs { inherit system; };
          libvfn = vfn.packages.${system}.default;
        });
    in {
      # used when calling `nix fmt <path/to/flake.nix>`
      formatter = forAllSystems ({ pkgs }: pkgs.nixfmt);

      # nix develop <flake-ref>#<name>
      # --
      # $ nix develop <flake-ref>#blue
      # $ nix develop <flake-ref>#yellow
      devShells = forAllSystems ({ pkgs, libvfn }: {
        default = pkgs.mkShell {
          name = "py3";
          nativeBuildInputs = with pkgs;
            [
              python3
              pyright
              meson
              ninja
              pkg-config
            ];
          buildInputs = with pkgs; [
            stdenv.cc.cc.lib
            gcc-unwrapped.lib
            libnvme
          ] ++ [libvfn];
          #PKG_CONFIG_PATH = "${libvfn}/lib/pkgconfig:${pkgs.libnvme}/lib/pkgconfig";
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc.lib
            pkgs.gcc-unwrapped.lib
            pkgs.libnvme
            libvfn
          ];
        };
      });
    };
}
