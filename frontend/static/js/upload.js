(function () {
  "use strict";

  const MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024;
  const tokenInput = document.getElementById("token");
  const form = document.getElementById("upload-form");
  const fileInput = document.getElementById("video-file");
  const button = document.getElementById("upload-button");
  const progressBar = document.getElementById("progress-bar");
  const statusText = document.getElementById("upload-status");

  tokenInput.value = localStorage.getItem("access_token") || "";
  tokenInput.addEventListener("input", function () {
    localStorage.setItem("access_token", tokenInput.value.trim());
  });

  function setStatus(message, isError) {
    statusText.textContent = message;
    statusText.classList.toggle("text-red-600", Boolean(isError));
    statusText.classList.toggle("text-gray-600", !isError);
  }

  function setProgress(percent) {
    progressBar.style.width = Math.max(0, Math.min(100, percent)) + "%";
  }

  function apiError(response, fallback) {
    return response.json().then(function (body) {
      if (typeof body.detail === "string") {
        return body.detail;
      }
      if (Array.isArray(body.detail)) {
        return body.detail.map(function (item) { return item.msg; }).join("; ");
      }
      return fallback;
    }).catch(function () {
      return fallback;
    });
  }

  async function completeUpload(videoId, token) {
    const response = await fetch("/videos/" + encodeURIComponent(videoId) + "/complete-upload", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token }
    });
    if (!response.ok) {
      throw new Error(await apiError(response, "Не удалось завершить загрузку"));
    }
    return response.json();
  }

  function uploadToMinio(uploadUrl, file, onProgress) {
    return new Promise(function (resolve, reject) {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", uploadUrl, true);
      xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

      xhr.upload.onprogress = function (event) {
        if (event.lengthComputable) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress(100);
          resolve();
        } else {
          reject(new Error("MinIO вернул HTTP " + xhr.status));
        }
      };
      xhr.onerror = function () { reject(new Error("Сетевая ошибка при загрузке в MinIO")); };
      xhr.onabort = function () { reject(new Error("Загрузка отменена")); };
      xhr.send(file);
    });
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const token = tokenInput.value.trim();
    const file = fileInput.files && fileInput.files[0];
    if (!token) {
      setStatus("Вставьте access token, полученный при логине.", true);
      return;
    }
    if (!file) {
      setStatus("Выберите видеофайл.", true);
      return;
    }
    if (!file.type || !file.type.startsWith("video/")) {
      setStatus("Разрешены только файлы video/*.", true);
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setStatus("Файл превышает лимит 2 ГБ.", true);
      return;
    }

    button.disabled = true;
    setProgress(0);
    setStatus("Резервируем загрузку…", false);

    try {
      const initResponse = await fetch("/videos/init-upload", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + token,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type,
          file_size: file.size,
          title: file.name.replace(/\.[^.]+$/, "")
        })
      });
      if (!initResponse.ok) {
        throw new Error(await apiError(initResponse, "Не удалось инициализировать загрузку"));
      }
      const initData = await initResponse.json();

      setStatus("Загружаем файл напрямую в MinIO…", false);
      await uploadToMinio(initData.upload_url, file, function (percent) {
        setProgress(percent);
        setStatus("Загрузка: " + percent + "%", false);
      });

      setStatus("Файл загружен. Запускаем обработку…", false);
      await completeUpload(initData.video_id, token);
      setStatus("Готово! Переходим к просмотру…", false);
      window.location.href = "/watch/" + initData.video_id;
    } catch (error) {
      setStatus(error.message || "Ошибка загрузки", true);
      button.disabled = false;
    }
  });
})();