(() => {
  let theme = "system",
    language = navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
  try {
    const t = localStorage.getItem("dsb-theme"),
      l = localStorage.getItem("dsb-lang");
    if (["system", "dark", "light"].includes(t)) theme = t;
    if (["zh", "en"].includes(l)) language = l;
  } catch {}
  document.documentElement.dataset.preference = theme;
  document.documentElement.dataset.theme =
    theme === "system"
      ? matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
})();
