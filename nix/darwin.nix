# nix-darwin module: launchd USER agent for a scheduled job on the mac mini.
# Generalized from notion-finance-sync. Runs as the login user so it has the
# login Keychain (op token), Messages DB, Chrome profiles, and Full Disk
# Access when the job needs them.
#
# Things Nix CANNOT do (document in the consuming repo's README):
#   - store the 1Password token in the Keychain (`just store-op-token`)
#   - grant Full Disk Access (TCC is SIP-protected)
{ config, lib, pkgs, ... }:

let
  cfg = config.services.notion-contact-sync;
in
{
  options.services.notion-contact-sync = {
    enable = lib.mkEnableOption "the notion-contact-sync contact unifier job";

    user = lib.mkOption {
      type = lib.types.str;
      description = "Login user the job runs as.";
      example = "alexmiller";
    };

    checkoutDir = lib.mkOption {
      type = lib.types.str;
      description = "Absolute path to the cloned repo (writable, in the user's home).";
      example = "/Users/alexmiller/notion-contact-sync";
    };

    hour = lib.mkOption {
      type = lib.types.int;
      default = 3;
      description = "Hour (0-23, local time) the job fires.";
    };

    minute = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Minute the job fires.";
    };

    keychainService = lib.mkOption {
      type = lib.types.str;
      default = "notion-contact-sync-op-token";
      description = "Keychain generic-password service name holding the 1Password SA token.";
    };

    opPackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs._1password-cli;
      defaultText = lib.literalExpression "pkgs._1password-cli";
      description = "The 1Password CLI package.";
    };
  };

  config = lib.mkIf cfg.enable {
    launchd.user.agents.notion-contact-sync = {
      serviceConfig = {
        Label = "com.alexmiller.notion-contact-sync";
        ProgramArguments = [
          "/bin/bash"
          "${cfg.checkoutDir}/scripts/run.sh"
        ];
        StartCalendarInterval = [
          { Hour = cfg.hour; Minute = cfg.minute; }
        ];
        RunAtLoad = false;
        StandardOutPath = "${cfg.checkoutDir}/data/launchd.log";
        StandardErrorPath = "${cfg.checkoutDir}/data/launchd.err.log";
        EnvironmentVariables = {
          PROJECT_DIR = cfg.checkoutDir;
          OP_TOKEN_KEYCHAIN_SERVICE = cfg.keychainService;
          PATH = lib.concatStringsSep ":" [
            (lib.makeBinPath [ pkgs.bash pkgs.coreutils cfg.opPackage ])
            "/etc/profiles/per-user/${cfg.user}/bin"
            "/Users/${cfg.user}/.nix-profile/bin"
            "/usr/bin"
            "/bin"
            "/usr/sbin"
            "/sbin"
          ];
        };
      };
    };
  };
}
