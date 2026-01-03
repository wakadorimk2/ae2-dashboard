// @ts-check

// Legacy shim: load the module entry for pages still pointing at app.js.
(() => {
  const script = document.createElement("script");
  script.type = "module";
  script.src = "/dashboard/ui/static/ui/main.js";
  document.head.appendChild(script);
})();
