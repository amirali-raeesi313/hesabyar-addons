/** @odoo-module **/

/**
 * Apply the saved Liquid Glass colour scheme before Owl mounts.
 *
 * Odoo chooses the light/dark asset variant on the server from the
 * `color_scheme` cookie.  Keeping a small boot record lets the reactive theme
 * service below know whether the bundle currently in memory matches the
 * requested scheme, even after this script has normalised that cookie.
 */
(function liquidThemeBoot() {
    const STORAGE_KEY = "liquid-theme";
    const COOKIE_KEY = "color_scheme";
    const DEFAULT_THEME = "dark";

    const normaliseTheme = (value) => (value === "light" ? "light" : DEFAULT_THEME);

    const readCookie = () => {
        const prefix = `${COOKIE_KEY}=`;
        let cookieString = "";
        try {
            cookieString = document.cookie;
        } catch {
            return undefined;
        }
        const entry = cookieString
            .split(";")
            .map((part) => part.trim())
            .find((part) => part.startsWith(prefix));
        if (!entry) {
            return undefined;
        }
        const value = entry.slice(prefix.length);
        try {
            return decodeURIComponent(value);
        } catch {
            return value;
        }
    };

    let storedTheme;
    try {
        storedTheme = window.localStorage.getItem(STORAGE_KEY);
    } catch {
        // Storage can be unavailable in hardened/private browser contexts.
    }

    // Honour Odoo's own colour-scheme cookie when localStorage is unavailable
    // (or intentionally disabled by a hardened browser). This keeps the user's
    // light-theme choice stable across the bundle-switch reload as well.
    const theme = normaliseTheme(storedTheme || readCookie());
    const bundleTheme = readCookie() === "dark" ? "dark" : "light";
    const root = document.documentElement;

    root.classList.toggle("liquid-dark", theme === "dark");
    root.classList.toggle("liquid-light", theme === "light");
    root.dataset.liquidTheme = theme;
    root.dataset.lgTheme = theme;
    root.style.colorScheme = theme;

    try {
        window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
        // The reactive service uses Odoo's in-memory storage fallback later.
    }

    if (readCookie() !== theme) {
        try {
            document.cookie = `${COOKIE_KEY}=${encodeURIComponent(theme)}; path=/; max-age=31536000; SameSite=Lax`;
        } catch {
            // The service verifies the cookie before attempting a bundle reload.
        }
    }

    window.__liquidThemeBoot = Object.freeze({
        theme,
        bundleTheme,
        needsBundleReload: bundleTheme !== theme,
    });
})();
