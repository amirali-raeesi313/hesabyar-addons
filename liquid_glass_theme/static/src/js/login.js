/** @odoo-module **/

/*
 * Progressive enhancement for Odoo's native /web/login form.
 * Nothing here prevents submission or changes the authentication payload.
 */
(function () {
    "use strict";

    const root = document.documentElement;
    const THEME_KEY = "liquid-theme";
    const VALID_THEMES = new Set(["dark", "light"]);

    function readCookie(name) {
        const prefix = `${encodeURIComponent(name)}=`;
        const item = document.cookie
            .split(";")
            .map((part) => part.trim())
            .find((part) => part.startsWith(prefix));
        return item ? decodeURIComponent(item.slice(prefix.length)) : null;
    }

    function readStoredTheme() {
        try {
            const value = localStorage.getItem(THEME_KEY);
            return VALID_THEMES.has(value) ? value : null;
        } catch {
            return null;
        }
    }

    function resolveTheme() {
        const storedTheme = readStoredTheme();
        if (storedTheme) {
            return storedTheme;
        }
        const odooColorScheme = readCookie("color_scheme");
        if (VALID_THEMES.has(odooColorScheme)) {
            return odooColorScheme;
        }
        return "dark";
    }

    function persistTheme(theme) {
        try {
            localStorage.setItem(THEME_KEY, theme);
        } catch {
            // Storage can be unavailable in strict/private browser contexts.
        }
        document.cookie = `color_scheme=${encodeURIComponent(theme)}; path=/; max-age=31536000; SameSite=Lax`;
    }

    function syncThemeButton(theme) {
        const button = document.querySelector(".o_liquid_login_theme_toggle");
        if (!button) {
            return;
        }
        const dark = theme === "dark";
        const label = dark ? "فعال‌کردن تم روشن" : "فعال‌کردن تم تاریک";
        const icon = button.querySelector(".o_liquid_login_theme_icon");
        const hiddenLabel = button.querySelector(".o_liquid_login_theme_label");

        button.setAttribute("aria-label", label);
        button.setAttribute("aria-pressed", dark ? "true" : "false");
        button.setAttribute("title", label);
        if (icon) {
            icon.textContent = dark ? "☀" : "☾";
        }
        if (hiddenLabel) {
            hiddenLabel.textContent = label;
        }
    }

    function applyTheme(theme, options = {}) {
        const normalizedTheme = VALID_THEMES.has(theme) ? theme : "dark";
        root.dataset.liquidLoginTheme = normalizedTheme;
        root.classList.toggle("liquid-dark", normalizedTheme === "dark");
        root.style.colorScheme = normalizedTheme;
        if (options.persist) {
            persistTheme(normalizedTheme);
        }
        syncThemeButton(normalizedTheme);
    }

    // Apply before DOMContentLoaded to minimize a light/dark flash.
    applyTheme(resolveTheme());

    function initializeThemeToggle() {
        const button = document.querySelector(".o_liquid_login_theme_toggle");
        if (!button || button.dataset.liquidBound === "true") {
            return;
        }
        button.dataset.liquidBound = "true";
        syncThemeButton(root.dataset.liquidLoginTheme || resolveTheme());
        button.addEventListener("click", () => {
            const currentTheme = root.dataset.liquidLoginTheme || resolveTheme();
            applyTheme(currentTheme === "dark" ? "light" : "dark", { persist: true });
        });
    }

    function initializePasswordToggle() {
        const input = document.getElementById("password");
        const button = document.querySelector(".o_liquid_password_toggle[aria-controls='password']");
        if (!input || !button || button.dataset.liquidBound === "true") {
            return;
        }
        button.dataset.liquidBound = "true";

        const icon = button.querySelector(".o_liquid_password_icon");
        const text = button.querySelector(".o_liquid_password_toggle_label");

        function setVisible(visible, focusInput = false) {
            input.type = visible ? "text" : "password";
            button.setAttribute("aria-pressed", visible ? "true" : "false");
            button.setAttribute("aria-label", visible ? "پنهان‌کردن رمز عبور" : "نمایش رمز عبور");
            if (text) {
                text.textContent = visible ? "پنهان" : "نمایش";
            }
            if (icon) {
                icon.classList.toggle("fa-eye", !visible);
                icon.classList.toggle("fa-eye-slash", visible);
            }
            if (focusInput) {
                try {
                    input.focus({ preventScroll: true });
                    const cursor = input.value.length;
                    input.setSelectionRange(cursor, cursor);
                } catch {
                    input.focus();
                }
            }
        }

        button.addEventListener("click", () => {
            setVisible(input.type === "password", true);
        });
        button._liquidResetPasswordVisibility = () => setVisible(false);
    }

    function initializeSubmitState() {
        const form = document.querySelector("form.o_liquid_login_form");
        const primaryButton = form && form.querySelector(".o_liquid_login_submit");
        if (!form || !primaryButton || form.dataset.liquidSubmitBound === "true") {
            return;
        }
        form.dataset.liquidSubmitBound = "true";

        const status = form.querySelector(".o_liquid_login_status");
        const defaultLabel = primaryButton.getAttribute("aria-label");

        function setLoading(loading) {
            form.classList.toggle("is-submitting", loading);
            form.setAttribute("aria-busy", loading ? "true" : "false");
            primaryButton.classList.toggle("is-loading", loading);
            primaryButton.setAttribute("aria-disabled", loading ? "true" : "false");
            if (loading) {
                primaryButton.setAttribute("aria-label", "در حال ورود");
                if (status) {
                    status.textContent = "در حال بررسی اطلاعات ورود";
                }
            } else {
                if (defaultLabel) {
                    primaryButton.setAttribute("aria-label", defaultLabel);
                } else {
                    primaryButton.removeAttribute("aria-label");
                }
                if (status) {
                    status.textContent = "";
                }
            }
        }

        form.addEventListener("submit", (event) => {
            // The debug-only superuser button has its own redirect value.
            // Leave that native submission completely untouched.
            if (event.submitter && event.submitter !== primaryButton) {
                return;
            }
            const showLoading = () => {
                if (!event.defaultPrevented) {
                    setLoading(true);
                }
            };
            if (typeof queueMicrotask === "function") {
                queueMicrotask(showLoading);
            } else {
                Promise.resolve().then(showLoading);
            }
        });

        form._liquidResetSubmitState = () => setLoading(false);
    }

    function initialize() {
        initializeThemeToggle();
        initializePasswordToggle();
        initializeSubmitState();
        applyTheme(root.dataset.liquidLoginTheme || resolveTheme());
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize, { once: true });
    } else {
        initialize();
    }

    window.addEventListener("storage", (event) => {
        if (event.key === THEME_KEY && VALID_THEMES.has(event.newValue)) {
            applyTheme(event.newValue);
        }
    });

    // Reset transient UI when the browser restores the login page from bfcache.
    window.addEventListener("pageshow", () => {
        const form = document.querySelector("form.o_liquid_login_form");
        if (form && typeof form._liquidResetSubmitState === "function") {
            form._liquidResetSubmitState();
        }
        const passwordButton = document.querySelector(".o_liquid_password_toggle");
        if (passwordButton && typeof passwordButton._liquidResetPasswordVisibility === "function") {
            passwordButton._liquidResetPasswordVisibility();
        }
    });
})();
