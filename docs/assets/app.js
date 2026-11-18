(function () {
  "use strict";

  function parseJsonScript(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "null");
    } catch (err) {
      console.error("Failed to parse JSON from", id, err);
      return null;
    }
  }

  // Escape text before it is inserted as HTML (reader source code contains "<", "&" etc.).
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Value is pre-rendered, already escaped HTML from llm_tools.code_translator.bullets_to_html.
  function pulletPointCellRenderer(params) {
    if (!params.value) return "";
    return `<p class="grid-bullets">${params.value}</p>`;
  }

  function codeCellRenderer(params) {
    if (!params.value) return "";
    return `<code class="grid-code">${escapeHtml(params.value)}</code>`;
  }

  function linkRenderer(params) {
    if (!params.value) return "";
    const dictType = (params.context && params.context.dictType) || "";
    const suffix = dictType === "profiles" ? ".json" : "";
    const name = escapeHtml(params.value);
    const href = `atch/server/${encodeURIComponent(dictType)}/${encodeURIComponent(params.value)}${suffix}`;
    return `<a href="${href}" download target="_blank" rel="noopener"
               aria-label="Download ${name}${suffix}">${name}</a>`;
  }

  function HeaderWithInfo() {
    this.eGui = null;
    this._destroyFns = [];
    this._popover = null;

    this.init = function (params) {
      const displayName = params.displayName || params.colDef.field || "";
      const infoText = (params.infoText || "").trim();

      const eGui = document.createElement("div");
      eGui.className = "ag-header-with-info";

      const title = document.createElement("span");
      title.className = "ag-header-title";
      title.textContent = displayName;
      eGui.appendChild(title);

      const menuButton = document.createElement("span");
      menuButton.className = "ag-header-cell-menu-button ag-header-menu-button";
      menuButton.setAttribute("role", "button");
      menuButton.setAttribute("tabindex", "0");
      menuButton.setAttribute("aria-label", `${displayName} menu`);
      menuButton.innerHTML = '<span class="ag-icon ag-icon-menu"></span>';
      eGui.appendChild(menuButton);

      const icon = document.createElement("span");
      icon.className = "ag-header-info";
      icon.setAttribute("role", "button");
      icon.setAttribute("tabindex", "0");
      icon.setAttribute("aria-label", `Information about column ${displayName}`);
      icon.setAttribute("aria-expanded", "false");
      icon.textContent = "i";
      eGui.appendChild(icon);

      if (!infoText) {
        icon.style.display = "none";
      }

      if (!params.enableMenu) {
        menuButton.style.display = "none";
      }

      const popover = document.createElement("div");
      popover.className = "ag-header-popover";
      popover.id = `ag-header-popover-${++HeaderWithInfo.counter}`;
      popover.setAttribute("role", "tooltip");
      icon.setAttribute("aria-controls", popover.id);
      popover.innerHTML = `
        <div class="ag-header-popover-title"></div>
        <div class="ag-header-popover-body"></div>
      `;
      popover.style.display = "none";
      document.body.appendChild(popover);

      const titleEl = popover.querySelector(".ag-header-popover-title");
      const bodyEl = popover.querySelector(".ag-header-popover-body");
      titleEl.textContent = displayName;
      bodyEl.innerHTML = escapeHtml(infoText).replace(/\n/g, "<br>");

      let isPinned = false;
      let hideTimeout = null;

      const positionPopover = () => {
        const rect = icon.getBoundingClientRect();
        popover.style.left = `${Math.max(12, rect.left + window.scrollX - 8)}px`;
        popover.style.top = `${rect.bottom + window.scrollY + 8}px`;
      };

      const showPopover = () => {
        if (!infoText) return;
        clearTimeout(hideTimeout);
        positionPopover();
        popover.style.display = "block";
        icon.setAttribute("aria-expanded", "true");
      };

      const hidePopover = () => {
        if (isPinned) return;
        popover.style.display = "none";
        icon.setAttribute("aria-expanded", "false");
      };

      const scheduleHide = () => {
        if (isPinned) return;
        clearTimeout(hideTimeout);
        hideTimeout = setTimeout(() => {
          if (!popover.matches(":hover") && !icon.matches(":hover")) {
            hidePopover();
          }
        }, 150);
      };

      const onIconEnter = () => showPopover();
      const onIconLeave = () => scheduleHide();
      const onPopoverEnter = () => clearTimeout(hideTimeout);
      const onPopoverLeave = () => scheduleHide();
      const onMenuClick = (event) => {
        event.stopPropagation();
        params.showColumnMenu(menuButton);
      };
      const onMenuKey = (event) => {
        if (event.key === "Enter" || event.key === " " || event.key === "ArrowDown") {
          event.preventDefault();
          onMenuClick(event);
        }
      };
      const onIconClick = (event) => {
        event.stopPropagation();
        isPinned = !isPinned;
        if (isPinned) {
          showPopover();
        } else {
          hidePopover();
        }
      };
      const onDocClick = (event) => {
        if (event.target === icon || popover.contains(event.target)) return;
        isPinned = false;
        hidePopover();
      };
      const onIconKey = (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onIconClick(event);
        } else if (event.key === "Escape") {
          isPinned = false;
          hidePopover();
        }
      };
      const onScroll = () => {
        if (popover.style.display === "block") {
          positionPopover();
        }
      };
      const onResize = () => onScroll();

      menuButton.addEventListener("click", onMenuClick);
      menuButton.addEventListener("keydown", onMenuKey);
      icon.addEventListener("mouseenter", onIconEnter);
      icon.addEventListener("mouseleave", onIconLeave);
      icon.addEventListener("click", onIconClick);
      icon.addEventListener("keydown", onIconKey);
      icon.addEventListener("focus", onIconEnter);
      icon.addEventListener("blur", onIconLeave);
      popover.addEventListener("mouseenter", onPopoverEnter);
      popover.addEventListener("mouseleave", onPopoverLeave);
      document.addEventListener("click", onDocClick);
      window.addEventListener("scroll", onScroll, true);
      window.addEventListener("resize", onResize);

      this._destroyFns.push(() => menuButton.removeEventListener("click", onMenuClick));
      this._destroyFns.push(() => menuButton.removeEventListener("keydown", onMenuKey));
      this._destroyFns.push(() => icon.removeEventListener("mouseenter", onIconEnter));
      this._destroyFns.push(() => icon.removeEventListener("mouseleave", onIconLeave));
      this._destroyFns.push(() => icon.removeEventListener("click", onIconClick));
      this._destroyFns.push(() => icon.removeEventListener("keydown", onIconKey));
      this._destroyFns.push(() => icon.removeEventListener("focus", onIconEnter));
      this._destroyFns.push(() => icon.removeEventListener("blur", onIconLeave));
      this._destroyFns.push(() => popover.removeEventListener("mouseenter", onPopoverEnter));
      this._destroyFns.push(() => popover.removeEventListener("mouseleave", onPopoverLeave));
      this._destroyFns.push(() => document.removeEventListener("click", onDocClick));
      this._destroyFns.push(() => window.removeEventListener("scroll", onScroll, true));
      this._destroyFns.push(() => window.removeEventListener("resize", onResize));

      this.eGui = eGui;
      this._popover = popover;
    };

    this.getGui = function () {
      return this.eGui;
    };

    this.destroy = function () {
      this._destroyFns.forEach((fn) => fn());
      this._destroyFns = [];
      if (this._popover) {
        this._popover.remove();
        this._popover = null;
      }
    };
  }

  HeaderWithInfo.counter = 0;

  function createGridFromElement(gridEl) {
    const gridId = gridEl.id;
    const columnDefs = parseJsonScript(`${gridId}-column-defs`);
    const rowData = parseJsonScript(`${gridId}-row-data`);
    const dictType = gridEl.dataset.dictType || "";

    if (!columnDefs || !rowData) return;

    const gridOptions = {
      theme: "legacy",
      // Privacy: never fetch fonts from Google (only relevant for the Theming API, set anyway).
      loadThemeGoogleFonts: false,
      columnDefs,
      rowData,
      enableCellTextSelection: true,
      defaultColDef: {
        flex: 1,
        sortable: true,
        filter: true,
        floatingFilter: true,
        resizable: true,
        wrapText: true,
        autoHeight: true
      },
      components: {
        codeCellRenderer,
        linkRenderer,
        HeaderWithInfo,
        pulletPointCellRenderer
      },
      context: {
        dictType
      }
    };

    agGrid.createGrid(gridEl, gridOptions);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof agGrid === "undefined") {
      console.error("AG Grid failed to load (docs/assets/vendor/). Tables cannot be rendered.");
      return;
    }
    const grids = document.querySelectorAll(".ag-theme-alpine[data-dict-type]");
    grids.forEach(createGridFromElement);
  });
})();
