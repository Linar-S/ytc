(function () {
  "use strict";

  const page = document.getElementById("channel-page");
  if (!page) {
    return;
  }
  const channelId = page.dataset.channelId;
  const button = document.getElementById("subscribe-button");
  const subscriberCount = document.querySelector("[data-subscriber-count]");
  const videoCount = document.querySelector("[data-video-count]");
  const videosContainer = document.getElementById("channel-videos-container");
  const tokenInput = document.getElementById("channel-token");
  const status = document.getElementById("subscribe-status");

  tokenInput.value = localStorage.getItem("access_token") || "";
  tokenInput.addEventListener("input", function () {
    localStorage.setItem("access_token", tokenInput.value.trim());
    refreshChannel();
  });

  function token() {
    return tokenInput.value.trim();
  }

  function setSubscribed(subscribed) {
    button.dataset.subscribed = subscribed ? "true" : "false";
    button.textContent = subscribed ? "Отписаться" : "Подписаться";
  }

  function renderVideos(videos) {
    videosContainer.replaceChildren();
    if (!videos.length) {
      const empty = document.createElement("div");
      empty.className = "rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-gray-600";
      empty.textContent = "На канале пока нет доступных видео.";
      videosContainer.appendChild(empty);
      return;
    }

    const grid = document.createElement("div");
    grid.className = "grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4";
    videos.forEach(function (video) {
      const link = document.createElement("a");
      link.href = "/watch/" + encodeURIComponent(video.id);
      link.className = "group overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition hover:shadow-md";

      const preview = document.createElement("div");
      preview.className = "relative aspect-video w-full overflow-hidden bg-gray-900";
      if (video.thumbnail_url) {
        const image = document.createElement("img");
        image.src = video.thumbnail_url;
        image.alt = video.title;
        image.loading = "lazy";
        image.className = "h-full w-full object-cover transition group-hover:scale-105";
        preview.appendChild(image);
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "flex h-full w-full items-center justify-center text-sm text-gray-300";
        placeholder.textContent = "Нет превью";
        preview.appendChild(placeholder);
      }
      if (video.visibility === "private") {
        const badge = document.createElement("span");
        badge.className = "absolute left-2 top-2 rounded bg-gray-900/80 px-2 py-1 text-xs font-semibold text-white";
        badge.textContent = "Приватное";
        preview.appendChild(badge);
      }
      link.appendChild(preview);

      const body = document.createElement("div");
      body.className = "p-4";
      const title = document.createElement("h3");
      title.className = "line-clamp-2 text-sm font-semibold text-gray-900 sm:text-base";
      title.textContent = video.title;
      body.appendChild(title);
      const meta = document.createElement("p");
      meta.className = "mt-1 text-xs text-gray-500";
      meta.textContent = "♥ " + String(video.like_count || 0);
      body.appendChild(meta);
      link.appendChild(body);
      grid.appendChild(link);
    });
    videosContainer.appendChild(grid);
  }

  async function refreshChannel() {
    if (!token()) {
      return;
    }
    try {
      const response = await fetch("/channels/" + encodeURIComponent(channelId), {
        headers: { Authorization: "Bearer " + token() }
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setSubscribed(Boolean(data.is_subscribed));
      subscriberCount.textContent = String(data.subscriber_count);
      videoCount.textContent = String(data.video_count);
      renderVideos(data.videos);
    } catch (_error) {
      // Keep the server-rendered channel if the refresh fails.
    }
  }

  button.addEventListener("click", async function () {
    if (!token()) {
      status.textContent = "Вставьте access token, чтобы подписаться.";
      status.className = "text-xs text-red-600";
      return;
    }
    const subscribed = button.dataset.subscribed === "true";
    status.textContent = "Обновляем подписку…";
    status.className = "text-xs text-gray-500";
    try {
      const response = await fetch("/channels/" + encodeURIComponent(channelId) + "/subscribe", {
        method: subscribed ? "DELETE" : "POST",
        headers: { Authorization: "Bearer " + token() }
      });
      if (!response.ok) {
        throw new Error("Не удалось изменить подписку");
      }
      const data = await response.json();
      setSubscribed(Boolean(data.subscribed));
      subscriberCount.textContent = String(data.subscriber_count);
      status.textContent = data.subscribed ? "Вы подписаны." : "Подписка отменена.";
      status.className = "text-xs text-green-700";
    } catch (error) {
      status.textContent = error.message;
      status.className = "text-xs text-red-600";
    }
  });

  refreshChannel();
})();