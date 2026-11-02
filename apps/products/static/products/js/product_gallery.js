// apps/products/static/products/js/product_gallery.js

/* =======================================
    JAVASCRIPT ГАЛЕРЕИ + LIGHTBOX
=======================================  */

document.addEventListener("DOMContentLoaded", function () {

    // =========================
    // Элементы
    // =========================
    const mainImage = document.getElementById("main-image");
    const thumbs = document.querySelectorAll(".gallery-thumb-vertical");
    const currentPhoto = document.getElementById("current-photo");
    const totalPhotos = document.getElementById("total-photos");

    const lightbox = document.getElementById("lightbox");
    const lightboxImage = document.getElementById("lightbox-image");
    const lightboxCurrent = document.getElementById("lightbox-current");
    const lightboxTotal = document.getElementById("lightbox-total");
    const lightboxThumbs = document.getElementById("lightbox-thumbs");
    const lightboxClose = document.querySelector(".lightbox-close");
    const lightboxPrev = document.querySelector(".lightbox-prev");
    const lightboxNext = document.querySelector(".lightbox-next");

    let returnFocus = null;
    let currentIndex = 0;
    let imageList = [];

    // =========================
    // Проверка наличия главного изображения
    // =========================
    if (!mainImage) {
        return;
    }

    // =========================
    // Формируем список изображений
    // =========================
    if (thumbs.length > 0) {
        // Если есть миниатюры — используем их
        thumbs.forEach(function(thumb) {
            imageList.push({
                src: thumb.dataset.full || thumb.src,
                alt: thumb.alt || "Фото товара"
            });
        });
    } else if (mainImage.src) {
        // Если миниатюр нет, но есть главное фото — создаём одно изображение
        imageList.push({
            src: mainImage.src,
            alt: mainImage.alt || "Фото товара"
        });
        // Создаём виртуальную миниатюру для отображения (скрытую)
        const virtualThumb = document.createElement('img');
        virtualThumb.src = mainImage.src;
        virtualThumb.dataset.full = mainImage.src;
        virtualThumb.alt = mainImage.alt || "Фото товара";
        virtualThumb.className = 'gallery-thumb-vertical active';
        virtualThumb.style.display = 'none';
        // Добавляем в DOM, чтобы JS мог её найти
        const container = document.querySelector('.gallery-thumbs-vertical');
        if (container) {
            container.appendChild(virtualThumb);
        }
        // Обновляем список thumbs
        document.querySelectorAll(".gallery-thumb-vertical");
    }

    // Если нет изображений — выходим
    if (imageList.length === 0) {
        return;
    }

    // =========================
    // Обновление счётчика
    // =========================
    function updateCounter() {
        if (currentPhoto) {
            currentPhoto.textContent = currentIndex + 1;
        }
        if (lightboxCurrent) {
            lightboxCurrent.textContent = currentIndex + 1;
        }
        if (totalPhotos) {
            totalPhotos.textContent = imageList.length;
        }
        if (lightboxTotal) {
            lightboxTotal.textContent = imageList.length;
        }
    }

    // =========================
    // Переключение главного изображения
    // =========================
    function showImage(index) {
        if (index < 0) index = imageList.length - 1;
        if (index >= imageList.length) index = 0;
        currentIndex = index;

        // Обновляем активную миниатюру (если есть)
        const allThumbs = document.querySelectorAll(".gallery-thumb-vertical");
        if (allThumbs.length > 0) {
            allThumbs.forEach(t => t.classList.remove("active"));
            if (allThumbs[index]) {
                allThumbs[index].classList.add("active");
            }
        }

        const imgData = imageList[index];
        if (imgData) {
            mainImage.src = imgData.src;
            mainImage.alt = imgData.alt;
        }

        updateCounter();
    }

    // =========================
    // Открытие лайтбокса
    // =========================
    function openLightbox(index) {
        if (index < 0) index = imageList.length - 1;
        if (index >= imageList.length) index = 0;
        currentIndex = index;

        const imgData = imageList[index];
        if (imgData) {
            lightboxImage.src = imgData.src;
            lightboxImage.alt = imgData.alt;
        }
        updateCounter();
        renderLightboxThumbs();
        const wasOpen = lightbox.classList.contains("show");
        if (!wasOpen) returnFocus = document.activeElement;
        lightbox.classList.add("show");
        if (!wasOpen) lightboxClose?.focus();
        document.body.style.overflow = "hidden";
    }

    // =========================
    // Закрытие лайтбокса
    // =========================
    function closeLightbox() {
        showImage(currentIndex);
        lightbox.classList.remove("show");
        returnFocus?.focus();
        document.body.style.overflow = "";
    }


    // =========================
    // Рендер миниатюр внутри лайтбокса
    // =========================
    function renderLightboxThumbs() {
        lightboxThumbs.innerHTML = "";

        // Если всего одно фото — не показываем миниатюры в лайтбоксе
        if (imageList.length <= 1) {
            lightboxThumbs.style.display = 'none';
            return;
        }

        lightboxThumbs.style.display = 'flex';

        imageList.forEach(function(imgData, index) {
            const img = document.createElement("img");
            img.src = imgData.src;
            img.className = "lightbox-thumb";
            if (index === currentIndex) {
                img.classList.add("active");
            }

            img.addEventListener("click", function (e) {
                e.stopPropagation();
                currentIndex = index;
                lightboxImage.src = imageList[index].src;
                lightboxImage.alt = imageList[index].alt;
                updateCounter();
                renderLightboxThumbs();
            });

            lightboxThumbs.appendChild(img);
        });
    }

    // =========================
    // Обработчики событий
    // =========================

    // Клик по миниатюре – переключение главного изображения
    const allThumbs = document.querySelectorAll(".gallery-thumb-vertical");
    if (allThumbs.length > 0) {
        allThumbs.forEach(function(thumb, index) {
            (thumb.closest("button") || thumb).addEventListener("click", function (e) {
                e.preventDefault();
                showImage(index);
            });
        });
    }

    // Стрелки переключения фото
    const prevBtn = document.getElementById('prev-image-btn');
    const nextBtn = document.getElementById('next-image-btn');

    if (prevBtn) {
        prevBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            showImage(currentIndex - 1);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            showImage(currentIndex + 1);
        });
    }

    // Клик по главному изображению – открытие лайтбокса
    (mainImage.closest("button") || mainImage).addEventListener("click", function () {
        openLightbox(currentIndex);
    });

    // Крестик закрытия
    if (lightboxClose) {
        lightboxClose.addEventListener("click", function (e) {
            e.stopPropagation();
            closeLightbox();
        });
    }

    // Стрелки в лайтбоксе
    if (lightboxPrev && lightboxNext) {
        lightboxPrev.addEventListener("click", function (e) {
            e.stopPropagation();
            openLightbox(currentIndex - 1);
        });

        lightboxNext.addEventListener("click", function (e) {
            e.stopPropagation();
            openLightbox(currentIndex + 1);
        });
    }

    // Закрытие по клику на фон
    lightbox.addEventListener("click", function (e) {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    // Клавиши
    document.addEventListener("keydown", function (e) {
        if (lightbox.classList.contains("show") && e.key === "Tab") {
            const controls = Array.from(lightbox.querySelectorAll('button:not([disabled]), a[href]'));
            const first = controls[0], last = controls[controls.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
            return;
        }
        if (lightbox.classList.contains("show")) {
            if (e.key === "Escape") {
                closeLightbox();
            } else if (e.key === "ArrowLeft") {
                openLightbox(currentIndex - 1);
            } else if (e.key === "ArrowRight") {
                openLightbox(currentIndex + 1);
            }
        } else {
            if (e.target.closest('input, textarea, select, [contenteditable="true"]') ||
                document.querySelector('.car-inquiry__modal:not([hidden]), #review-lightbox.show')) return;
            if (imageList.length > 1) {
                if (e.key === "ArrowLeft") {
                    showImage(currentIndex - 1);
                } else if (e.key === "ArrowRight") {
                    showImage(currentIndex + 1);
                }
            }
        }
    });

    // =========================
    // Инициализация
    // =========================
    // Определяем активную миниатюру
    const activeThumb = document.querySelector(".gallery-thumb-vertical.active");
    if (activeThumb) {
        const allThumbsArray = Array.from(document.querySelectorAll(".gallery-thumb-vertical"));
        const activeIndex = allThumbsArray.indexOf(activeThumb);
        if (activeIndex !== -1 && activeIndex < imageList.length) {
            showImage(activeIndex);
        } else {
            showImage(0);
        }
    } else {
        showImage(0);
    }

});