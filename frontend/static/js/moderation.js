(function () {
  "use strict";

  const tokenInput = document.getElementById("moderation-token");
  const status = document.getElementById("moderation-status");
  const queue = document.getElementById("moderation-queue");

  tokenInput.value = localStorage.getItem("access_token") || "";
  tokenInput.addEventListener("input", function () {
    localStorage.setItem("access_token", tokenInput.value.trim());
    loadQueue();
  });

  function token() {
    return tokenInput.value.trim();
  }

  function setStatus(message, isError) {
    status.textContent = message;
    status.className = "mt-1 text-xs " + (isError ? "text-red-700" : "text-amber-800");
  }

  function renderQueue(items) {
    queue.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500";
      empty.textContent = "Очередь жалоб пуста.";
      queue.appendChild(empty);
      return;
    }

    items.forEach(function (item) {
      const card = document.createElement("article");
      card.className = "rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5";

      const header = document.createElement("div");
      header.className = "flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between";
      const info = document.createElement("div");
      const title = document.createElement("h2");
      title.className = "text-base font-semibold text-gray-900";
      title.textContent = item.title;
      const meta = document.createElement("p");
      meta.className = "mt-1 text-xs text-gray-500";
      meta.textContent = (item.owner_username || "Автор") + " · жалоб: " + item.report_count + " · статус: " + item.status;
      info.appendChild(title);
      info.appendChild(meta);
      header.appendChild(info);

      const button = document.createElement("button");
      button.type = "button";
      button.className = item.status === "hidden"
        ? "inline-flex items-center justify-center rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"
        : "inline-flex items-center justify-center rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700";
      button.textContent = item.status === "hidden" ? "Unhide" : "Hide";
      button.addEventListener("click", function () {
        moderate(item.id, item.status === "hidden" ? "unhide" : "hide");
      });
      header.appendChild(button);
      card.appendChild(header);
      queue.appendChild(card);
    });
  }

  async function loadQueue() {
    if (!token()) {
      return;
    }
    setStatus("Загружаем очередь…", false);
    try {
      const response = await fetch("/moderation/queue", {
        headers: { Authorization: "Bearer " + token() }
      });
      if (!response.ok) {
        const body = await response.json().catch(function () { return {}; });
        throw new Error(typeof body.detail === "string" ? body.detail : "Доступ запрещён");
      }
      const data = await response.json();
      renderQueue(data.items || []);
      setStatus("Очередь загружена.", false);
    } catch (error) {
      queue.replaceChildren();
      const errorBox = document.createElement("div");
      errorBox.className = "rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-700";
      errorBox.textContent = error.message;
      queue.appendChild(errorBox);
      setStatus(error.message, true);
    }
  }

  async function moderate(videoId, action) {
    try {
      const response = await fetch("/moderation/videos/" + encodeURIComponent(videoId) + "/" + action, {
        method: "POST",
        headers: { Authorization: "Bearer " + token() }
      });
      if (!response.ok) {
        throw new Error("Не удалось изменить статус видео");
      }
      await loadQueue();
    } catch (error) {
      setStatus(error.message, true);
    }
  }

  loadQueue();
})();