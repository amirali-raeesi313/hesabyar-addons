/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

import {
    Component,
    onWillUnmount,
    reactive,
    useEffect,
    useExternalListener,
    useRef,
    useState,
} from "@odoo/owl";

const THEME_STORAGE_KEY = "liquid-theme";
const THEME_COOKIE_KEY = "color_scheme";
const THEME_RELOAD_GUARD_KEY = "liquid-theme-bundle-reload";
const SIDEBAR_STORAGE_KEY = "liquid-sidebar-collapsed";
const DEFAULT_THEME = "dark";

const ROOT_SHELL_CLASSES = [
    "liquid-sidebar-ready",
    "liquid-sidebar-desktop",
    "liquid-sidebar-collapsed",
    "liquid-sidebar-mobile-open",
    "liquid-app-grid-open",
];

const FOCUSABLE_SELECTOR = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    '[tabindex]:not([tabindex="-1"])',
].join(",");

function normaliseTheme(value) {
    return value === "light" ? "light" : DEFAULT_THEME;
}

function normaliseBundleTheme(value) {
    return value === "dark" ? "dark" : "light";
}

function normaliseSearchText(value) {
    return String(value || "")
        .trim()
        .normalize("NFKC")
        .replace(/[\u064B-\u065F\u0670]/g, "")
        .replace(/\u064A/g, "ی")
        .replace(/\u0643/g, "ک")
        .replace(/[\u200C\u200D]/g, "")
        .replace(/\s+/g, " ")
        .toLocaleLowerCase();
}

function safeStorageGet(storage, key) {
    try {
        return storage.getItem(key);
    } catch {
        return null;
    }
}

function safeStorageSet(storage, key, value) {
    try {
        storage.setItem(key, value);
    } catch {
        // Odoo's browser helper normally provides an in-memory fallback.
    }
}

function safeStorageRemove(storage, key) {
    try {
        storage.removeItem(key);
    } catch {
        // A missing persistence layer must not make the shell unusable.
    }
}

function safeThemeCookieGet() {
    try {
        return cookie.get(THEME_COOKIE_KEY);
    } catch {
        return undefined;
    }
}

function safeThemeCookieSet(theme) {
    try {
        cookie.set(THEME_COOKIE_KEY, theme);
    } catch {
        // CSS state still works; the service skips a futile bundle reload.
    }
}

function focusElement(element) {
    if (!element || !element.isConnected || !element.getClientRects().length) {
        return;
    }
    try {
        element.focus({ preventScroll: true });
    } catch {
        element.focus();
    }
}

function trapFocus(container, event) {
    if (!container || event.key !== "Tab") {
        return;
    }
    const focusableElements = [...container.querySelectorAll(FOCUSABLE_SELECTOR)].filter(
        (element) => element.getClientRects().length && element.getAttribute("aria-hidden") !== "true"
    );
    if (!focusableElements.length) {
        event.preventDefault();
        return;
    }
    const first = focusableElements[0];
    const last = focusableElements[focusableElements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        focusElement(last);
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        focusElement(first);
    }
}

/**
 * Theme state shared by every Liquid Glass component.
 *
 * Odoo's SCSS bundle is selected server-side from `color_scheme`.  The service
 * therefore reloads only when the already loaded bundle differs from the new
 * choice. Cookie verification and a session guard prevent futile reload loops.
 */
export const liquidThemeService = {
    start(env) {
        const bootState = window.__liquidThemeBoot;
        const initialTheme = normaliseTheme(
            safeStorageGet(browser.localStorage, THEME_STORAGE_KEY) || bootState?.theme
        );
        const loadedBundleTheme = normaliseBundleTheme(
            bootState?.bundleTheme || safeThemeCookieGet()
        );

        const state = reactive({
            theme: initialTheme,
            isReloading: false,
            get isDark() {
                return this.theme === "dark";
            },
        });

        const applyToDocument = (theme) => {
            const root = document.documentElement;
            root.classList.toggle("liquid-dark", theme === "dark");
            root.classList.toggle("liquid-light", theme === "light");
            root.dataset.liquidTheme = theme;
            root.dataset.lgTheme = theme;
            root.style.colorScheme = theme;
        };

        const syncThemeCookie = (theme) => {
            if (safeThemeCookieGet() !== theme) {
                safeThemeCookieSet(theme);
            }
            return safeThemeCookieGet() === theme;
        };

        const requestBundleReload = (theme) => {
            const guardedTheme = safeStorageGet(
                browser.sessionStorage,
                THEME_RELOAD_GUARD_KEY
            );
            if (guardedTheme === theme) {
                return false;
            }
            safeStorageSet(browser.sessionStorage, THEME_RELOAD_GUARD_KEY, theme);
            state.isReloading = true;
            browser.setTimeout(() => browser.location.reload(), 0);
            return true;
        };

        state.setTheme = (value) => {
            const theme = normaliseTheme(value);
            const changed = state.theme !== theme;

            state.theme = theme;
            applyToDocument(theme);
            safeStorageSet(browser.localStorage, THEME_STORAGE_KEY, theme);
            const cookieSynced = syncThemeCookie(theme);

            if (changed) {
                env.bus.trigger("LIQUID_THEME:CHANGED", { theme });
            }

            if (loadedBundleTheme !== theme && cookieSynced) {
                requestBundleReload(theme);
            } else {
                safeStorageRemove(browser.sessionStorage, THEME_RELOAD_GUARD_KEY);
                state.isReloading = false;
            }
            return theme;
        };

        state.toggle = () => state.setTheme(state.isDark ? "light" : "dark");

        applyToDocument(initialTheme);
        safeStorageSet(browser.localStorage, THEME_STORAGE_KEY, initialTheme);
        const cookieSynced = syncThemeCookie(initialTheme);
        if (loadedBundleTheme !== initialTheme && cookieSynced) {
            requestBundleReload(initialTheme);
        } else {
            safeStorageRemove(browser.sessionStorage, THEME_RELOAD_GUARD_KEY);
        }

        browser.addEventListener("storage", (event) => {
            if (event.key === THEME_STORAGE_KEY) {
                const theme = normaliseTheme(event.newValue);
                if (theme !== state.theme) {
                    state.setTheme(theme);
                }
            }
        });

        return state;
    },
};

/** Shared, persistent shell state for the systray and main component. */
export const liquidShellService = {
    start() {
        const state = reactive({
            collapsed: safeStorageGet(browser.localStorage, SIDEBAR_STORAGE_KEY) === "1",
            mobileOpen: false,
            appsOpen: false,
        });

        state.setCollapsed = (collapsed) => {
            state.collapsed = Boolean(collapsed);
            safeStorageSet(
                browser.localStorage,
                SIDEBAR_STORAGE_KEY,
                state.collapsed ? "1" : "0"
            );
        };
        state.toggleSidebar = (isSmall) => {
            if (isSmall) {
                state.appsOpen = false;
                state.mobileOpen = !state.mobileOpen;
            } else {
                state.setCollapsed(!state.collapsed);
            }
        };
        state.openMobile = () => {
            state.appsOpen = false;
            state.mobileOpen = true;
        };
        state.closeMobile = () => {
            state.mobileOpen = false;
        };
        state.openApps = () => {
            state.mobileOpen = false;
            state.appsOpen = true;
        };
        state.closeApps = () => {
            state.appsOpen = false;
        };
        state.toggleApps = () => {
            if (state.appsOpen) {
                state.closeApps();
            } else {
                state.openApps();
            }
        };

        browser.addEventListener("storage", (event) => {
            if (event.key === SIDEBAR_STORAGE_KEY) {
                state.collapsed = event.newValue === "1";
            }
        });

        return state;
    },
};

export class LiquidAppsToggle extends Component {
    static template = "liquid_glass_theme.AppsToggle";
    static props = {};

    setup() {
        this.shell = useState(useService("liquid_shell"));
    }

    toggle() {
        this.shell.toggleApps();
    }
}

export class LiquidSidebarToggle extends Component {
    static template = "liquid_glass_theme.SidebarToggle";
    static props = {};

    setup() {
        this.shell = useState(useService("liquid_shell"));
        this.ui = useState(useService("ui"));
    }

    get isExpanded() {
        return this.ui.isSmall ? this.shell.mobileOpen : !this.shell.collapsed;
    }

    get label() {
        return this.isExpanded ? "جمع کردن منوی کناری" : "باز کردن منوی کناری";
    }

    toggle() {
        this.shell.toggleSidebar(this.ui.isSmall);
    }
}

export class LiquidThemeToggle extends Component {
    static template = "liquid_glass_theme.ThemeToggle";
    static props = {};

    setup() {
        this.theme = useState(useService("liquid_theme"));
    }

    get label() {
        return this.theme.isDark ? "فعال کردن تم روشن" : "فعال کردن تم تاریک";
    }

    get iconClass() {
        return this.theme.isDark ? "fa fa-sun-o" : "fa fa-moon-o";
    }

    toggle() {
        if (!this.theme.isReloading) {
            this.theme.toggle();
        }
    }
}

/**
 * Persistent RTL desktop sidebar, mobile drawer, and searchable applications
 * overlay.  Every destination is provided by Odoo's menu service and opened
 * with `selectMenu`, preserving the standard action lifecycle and permissions.
 */
export class LiquidSidebar extends Component {
    static template = "liquid_glass_theme.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.shell = useState(useService("liquid_shell"));
        this.ui = useState(useService("ui"));
        this.state = useState({
            query: "",
            appQuery: "",
            revision: 0,
            selectedMenuId: null,
            busyMenuId: null,
            busyAppId: null,
        });

        this.sidebarPanel = useRef("sidebarPanel");
        this.sidebarSearch = useRef("sidebarSearch");
        this.appGrid = useRef("appGrid");
        this.appsSearch = useRef("appsSearch");

        const refreshMenus = () => {
            this.state.revision++;
        };
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            this.state.query = "";
            refreshMenus();
        });
        useBus(this.env.bus, "ACTION_MANAGER:UPDATE", refreshMenus);
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", refreshMenus);
        useExternalListener(window, "keydown", this.onWindowKeydown, { capture: true });

        useEffect(
            (isSmall) => {
                if (!isSmall && this.shell.mobileOpen) {
                    this.shell.closeMobile();
                }
            },
            () => [this.ui.isSmall]
        );

        useEffect(
            (isSmall, collapsed, mobileOpen, appsOpen) => {
                const root = document.documentElement;
                root.classList.add("liquid-sidebar-ready");
                root.classList.toggle("liquid-sidebar-desktop", !isSmall);
                root.classList.toggle("liquid-sidebar-collapsed", !isSmall && collapsed);
                root.classList.toggle("liquid-sidebar-mobile-open", isSmall && mobileOpen);
                root.classList.toggle("liquid-app-grid-open", appsOpen);
                document.body.classList.toggle("o_lg_sidebar_enabled", !isSmall);
                document.body.classList.toggle(
                    "o_lg_sidebar_collapsed",
                    !isSmall && collapsed
                );
            },
            () => [
                this.ui.isSmall,
                this.shell.collapsed,
                this.shell.mobileOpen,
                this.shell.appsOpen,
            ]
        );

        useEffect(
            (isOpen) => {
                if (isOpen) {
                    this._appsPreviousFocus = document.activeElement;
                    browser.requestAnimationFrame(() => focusElement(this.appsSearch.el));
                } else {
                    this.state.appQuery = "";
                    if (this._appsPreviousFocus) {
                        focusElement(this._appsPreviousFocus);
                        this._appsPreviousFocus = null;
                    }
                }
            },
            () => [this.shell.appsOpen]
        );

        useEffect(
            (isSmall, isOpen) => {
                if (isSmall && isOpen) {
                    this._sidebarPreviousFocus = document.activeElement;
                    browser.requestAnimationFrame(() => {
                        focusElement(
                            this.sidebarSearch.el ||
                                this.sidebarPanel.el?.querySelector(FOCUSABLE_SELECTOR)
                        );
                    });
                } else if (this._sidebarPreviousFocus) {
                    focusElement(this._sidebarPreviousFocus);
                    this._sidebarPreviousFocus = null;
                }
            },
            () => [this.ui.isSmall, this.shell.mobileOpen]
        );

        onWillUnmount(() => {
            document.documentElement.classList.remove(...ROOT_SHELL_CLASSES);
            document.body.classList.remove("o_lg_sidebar_enabled", "o_lg_sidebar_collapsed");
        });
    }

    onWindowKeydown(event) {
        if (event.key === "Escape") {
            if (this.shell.appsOpen) {
                event.preventDefault();
                event.stopPropagation();
                this.shell.closeApps();
            } else if (this.ui.isSmall && this.shell.mobileOpen) {
                event.preventDefault();
                event.stopPropagation();
                this.shell.closeMobile();
            }
            return;
        }
        if (this.shell.appsOpen) {
            trapFocus(this.appGrid.el, event);
        } else if (this.ui.isSmall && this.shell.mobileOpen) {
            trapFocus(this.sidebarPanel.el, event);
        }
    }

    get currentApp() {
        this.state.revision;
        return this.menuService.getCurrentApp();
    }

    get apps() {
        this.state.revision;
        return this.menuService.getApps() || [];
    }

    get filteredApps() {
        const query = normaliseSearchText(this.state.appQuery);
        if (!query) {
            return this.apps;
        }
        return this.apps.filter((app) => normaliseSearchText(this.appName(app)).includes(query));
    }

    get rawMenuEntries() {
        const currentApp = this.currentApp;
        if (!currentApp) {
            return [];
        }
        const cacheKey = `${currentApp.id}:${this.state.revision}`;
        if (this._menuEntriesCache?.key === cacheKey) {
            return this._menuEntriesCache.entries;
        }
        const root = this.menuService.getMenuAsTree(currentApp.id);
        const entries = [];

        const walk = (menus, depth, parentLabels, ancestorIds) => {
            for (const menu of menus || []) {
                const label = menu.name || "";
                const children = menu.childrenTree || [];
                const breadcrumb = [...parentLabels, label].filter(Boolean).join(" / ");
                entries.push({
                    menu,
                    label,
                    depth,
                    breadcrumb,
                    ancestorIds: [...ancestorIds],
                    isGroup: Boolean(children.length) || !menu.actionID,
                    searchText: normaliseSearchText(breadcrumb),
                });
                if (children.length) {
                    walk(children, depth + 1, [...parentLabels, label], [
                        ...ancestorIds,
                        menu.id,
                    ]);
                }
            }
        };

        walk(root.childrenTree || [], 0, [], []);
        this._menuEntriesCache = { key: cacheKey, entries };
        return entries;
    }

    get menuEntries() {
        const entries = this.rawMenuEntries;
        const query = normaliseSearchText(this.state.query);
        if (!query) {
            return entries;
        }

        const visibleIds = new Set();
        const matchedGroupIds = new Set();
        for (const entry of entries) {
            if (!entry.searchText.includes(query)) {
                continue;
            }
            visibleIds.add(entry.menu.id);
            entry.ancestorIds.forEach((id) => visibleIds.add(id));
            if (entry.isGroup) {
                matchedGroupIds.add(entry.menu.id);
            }
        }
        if (matchedGroupIds.size) {
            for (const entry of entries) {
                if (entry.ancestorIds.some((id) => matchedGroupIds.has(id))) {
                    visibleIds.add(entry.menu.id);
                }
            }
        }
        return entries.filter((entry) => visibleIds.has(entry.menu.id));
    }

    get activeEntry() {
        const entries = this.rawMenuEntries;
        const action = this.actionService.currentController?.action;
        const actionId = action?.id;
        const actionPath = action?.path;
        const cacheKey = [
            this.state.revision,
            this.currentApp?.id,
            actionId,
            actionPath,
            this.state.selectedMenuId,
        ].join(":");
        if (this._activeEntryCache?.key === cacheKey) {
            return this._activeEntryCache.entry;
        }
        const byAction = entries.find(
            (entry) =>
                !entry.isGroup &&
                ((actionId && String(entry.menu.actionID) === String(actionId)) ||
                    (actionPath && entry.menu.actionPath === actionPath))
        );
        const selected = entries.find(
            (entry) => entry.menu.id === this.state.selectedMenuId
        );
        const selectedMatchesAction = Boolean(
            selected &&
                ((actionId && String(selected.menu.actionID) === String(actionId)) ||
                    (actionPath && selected.menu.actionPath === actionPath))
        );
        const active =
            (selectedMatchesAction && selected) ||
            byAction ||
            ((!actionId && !actionPath && selected) || undefined);
        this._activeEntryCache = { key: cacheKey, entry: active };
        return active;
    }

    isEntryActive(entry) {
        const active = this.activeEntry;
        return Boolean(
            active &&
                (active.menu.id === entry.menu.id ||
                    (entry.isGroup && active.ancestorIds.includes(entry.menu.id)))
        );
    }

    appName(app) {
        return app?.name || app?.label || "برنامه";
    }

    appInitial(app) {
        return [...this.appName(app).trim()][0] || "•";
    }

    menuInitial(entry) {
        return [...String(entry?.label || "").trim()][0] || "•";
    }

    appIconData(app) {
        const iconData = app?.webIconData;
        if (!iconData || typeof iconData !== "string") {
            return null;
        }
        if (iconData.startsWith("data:") || iconData.startsWith("/") || iconData.startsWith("http")) {
            return iconData;
        }
        const prefix = iconData.startsWith("P")
            ? "data:image/svg+xml;base64,"
            : "data:image/png;base64,";
        return prefix + iconData.replace(/\s/g, "");
    }

    appIconSpec(app) {
        if (!app?.webIcon || typeof app.webIcon !== "string") {
            return null;
        }
        const [iconClass, color, backgroundColor] = app.webIcon.split(",");
        if (backgroundColor === undefined) {
            return null;
        }
        return {
            iconClass: iconClass || "fa fa-cube",
            color: color || "currentColor",
            backgroundColor: backgroundColor || "transparent",
        };
    }

    appIconStyle(app) {
        const icon = this.appIconSpec(app);
        return icon
            ? `color:${icon.color};background-color:${icon.backgroundColor};`
            : undefined;
    }

    menuDepthStyle(entry) {
        return `--lg-menu-depth:${Math.min(entry.depth, 6)};`;
    }

    async selectMenu(entry) {
        if (entry.isGroup || !entry.menu.actionID || this.state.busyMenuId) {
            return;
        }
        this.state.busyMenuId = entry.menu.id;
        try {
            await this.menuService.selectMenu(entry.menu);
            this.state.selectedMenuId = entry.menu.id;
            this.shell.closeMobile();
            this.shell.closeApps();
        } finally {
            this.state.busyMenuId = null;
        }
    }

    async selectApp(app) {
        if (!app?.actionID || this.state.busyAppId) {
            return;
        }
        this.state.busyAppId = app.id;
        try {
            await this.menuService.selectMenu(app);
            this.state.selectedMenuId = null;
            this.state.appQuery = "";
            this.shell.closeApps();
            this.shell.closeMobile();
        } finally {
            this.state.busyAppId = null;
        }
    }

    onMenuSearchKeydown(event) {
        if (event.key === "Enter") {
            const firstAction = this.menuEntries.find((entry) => !entry.isGroup);
            if (firstAction) {
                event.preventDefault();
                this.selectMenu(firstAction);
            }
        }
    }

    onAppsSearchKeydown(event) {
        if (event.key === "Enter" && this.filteredApps.length) {
            event.preventDefault();
            this.selectApp(this.filteredApps[0]);
        }
    }
}

registry.category("services").add("liquid_theme", liquidThemeService);
registry.category("services").add("liquid_shell", liquidShellService);

const systray = registry.category("systray");
systray.add(
    "liquid_glass_theme.apps_toggle",
    { Component: LiquidAppsToggle },
    { sequence: 12 }
);
systray.add(
    "liquid_glass_theme.sidebar_toggle",
    { Component: LiquidSidebarToggle },
    { sequence: 13 }
);
systray.add(
    "liquid_glass_theme.theme_toggle",
    { Component: LiquidThemeToggle },
    { sequence: 14 }
);

registry.category("main_components").add(
    "liquid_glass_theme.sidebar",
    { Component: LiquidSidebar },
    { sequence: 15 }
);
