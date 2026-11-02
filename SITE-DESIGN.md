# Local inference documentation design

The shared guideline is maintained in
[miyako/local-inference-site-design](https://github.com/miyako/local-inference-site-design/blob/main/SITE-DESIGN.md).
Swama adopts [v1.0.0](https://github.com/miyako/local-inference-site-design/blob/v1.0.0/SITE-DESIGN.md).

This is a documentation reference, not a submodule or build dependency.
Guideline updates are adopted explicitly alongside local implementation changes.

Local implementation: [site styles](assets/css/style.scss),
[syntax colors](assets/css/code.css), [layout](_layouts/default.html), and
[home page](index.html). This reference is excluded from generated Pages.

Site branding: `assets/swama.png` is an unchanged copy of the 4D project's
`swama/Resources/logo.png`, used for the sidebar, home-page engine icon, favicon,
and structured metadata. The original PNG and SVG logos live in the 4D project's
`swama/Resources` folder.

Local exceptions: none beyond the shared guideline's permitted engine-specific
content and branding (Swama, Swift/MLX, Apple Silicon requirements, model
directories, endpoints, and release details).
