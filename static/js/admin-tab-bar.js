// Shared mobile list/editor tab switching for admin/questions.html and admin/validate.html.
(function () {
  var tabBar = document.querySelector(".admin-tab-bar");
  if (!tabBar) return;
  var listPanel = document.querySelector('[data-panel="list"]');
  var editorPanel = document.querySelector('[data-panel="editor"]');
  var isMobile = window.innerWidth <= 768;
  function showPanel(name) {
    if (!isMobile) return;
    var isEditor = name === "editor";
    listPanel.classList.toggle("panel-hidden", isEditor);
    editorPanel.classList.toggle("panel-hidden", !isEditor);
    tabBar.querySelectorAll(".tab-btn").forEach(function (b) { b.classList.toggle("active", b.dataset.target === name); });
  }
  var hasSelection = tabBar.dataset.hasSelection === "true";
  if (isMobile) {
    if (hasSelection) {
      listPanel.classList.add("panel-hidden");
      tabBar.querySelector('[data-target="list"]').classList.remove("active");
      tabBar.querySelector('[data-target="editor"]').classList.add("active");
    } else {
      editorPanel.classList.add("panel-hidden");
      tabBar.querySelector('[data-target="list"]').classList.add("active");
      tabBar.querySelector('[data-target="editor"]').classList.remove("active");
    }
  }
  tabBar.querySelectorAll(".tab-btn").forEach(function (b) {
    b.addEventListener("click", function () { showPanel(b.dataset.target); });
  });
  listPanel.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () { if (isMobile) showPanel("editor"); });
  });
})();
