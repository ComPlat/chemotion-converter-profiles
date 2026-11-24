# Third-party assets (vendored)

This folder is the **only** place where third-party code is shipped with the website.
Everything is served from the same origin as the page itself (GitHub Pages). No CDN, no
external fonts, no external stylesheets, no analytics, no tracking. Visitors' browsers
therefore never contact a third-party server when the site is opened (GDPR / TDDDG).

| Package | Version | License | Why it is needed |
|---|---|---|---|
| [AG Grid Community](https://www.ag-grid.com/) | 36.2.0 | MIT (see `ag-grid-community-36.2.0/LICENSE.txt`) | Sortable, filterable data grids for the reader and profile tables on `index.html`. |

## Files and integrity

Taken unmodified from the npm package `ag-grid-community@36.2.0` (`npm pack ag-grid-community@36.2.0`):

| File | Source path in package | SHA-256 |
|---|---|---|
| `ag-grid-community.min.noStyle.js` | `dist/ag-grid-community.min.noStyle.js` | `3b05777f78aa10b6d7fd020bc2076936b889e5a0ff9c1a764fdbe6aa19456993` |
| `ag-grid.min.css` | `styles/ag-grid.min.css` | `f1cab681a9157b54dc8124e3add01c0189c9f20cc86f09879702c44f4411e778` |
| `ag-theme-alpine.min.css` | `styles/ag-theme-alpine.min.css` | `70ae2a7880e819a0d51125ffc6d04519da035f17c358075a8440706f414cc1df` |
| `LICENSE.txt` | `LICENSE.txt` | – |

The `noStyle` bundle is used on purpose: the regular bundle injects the CSS of *all* legacy themes
at runtime as `<style>` elements after `global.css`, which would override the site's colour tokens
(dark mode). With `noStyle`, only the two CSS files above are loaded, before `global.css`.

Privacy checks done before vendoring:

- The CSS files contain no `@import` and no `url(http…)` references (icons are embedded as data URIs).
- The JS bundle can load Google Fonts **only** through the newer Theming API with
  `loadThemeGoogleFonts: true`. The site uses the legacy CSS theme (`theme: "legacy"`) and
  additionally sets `loadThemeGoogleFonts: false` explicitly in `docs/assets/app.js`.

## Updating

1. `npm pack ag-grid-community@<version>` (pick a release that is at least a few weeks old).
2. Copy the four files listed above into a new folder `ag-grid-community-<version>/`.
3. Repeat the privacy checks (`grep -E "@import|url\(https?:" *.css`, `grep googleapis *.js`).
4. Update the paths in `profile_manager/index_template.html`, this README and the
   "Third-party components" section of `docs/privacy-en.html`.
5. Delete the old version folder.
