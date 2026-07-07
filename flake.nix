{
  description = "notion-contact-sync: unify social-platform contact exports into the Notion People DB";

  outputs = { self, ... }: {
    darwinModules.default = import ./nix/darwin.nix;
  };
}
