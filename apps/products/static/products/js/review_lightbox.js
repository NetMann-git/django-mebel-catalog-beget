// static/products/js/review_lightbox.js

document.addEventListener("DOMContentLoaded", function () {

    const lightbox = document.getElementById("review-lightbox");
    if (!lightbox) return;
    const lightboxImage = document.getElementById("review-lightbox-image");
    const lightboxCurrent = document.getElementById("review-lightbox-current");
    const lightboxTotal = document.getElementById("review-lightbox-total");
    const lightboxThumbs = document.getElementById("review-lightbox-thumbs");
    const lightboxClose = lightbox.querySelector(".lightbox-close");
    const lightboxPrev = lightbox.querySelector(".lightbox-prev");
    const lightboxNext = lightbox.querySelector(".lightbox-next");

    let currentIndex = 0;
    let images = [];

    // Все ссылки на фото в отзывах
    const reviewLinks = document.querySelectorAll(".review-image-link");

    if (reviewLinks.length === 0) return;

    // Собираем все фото
    reviewLinks.forEach(function(link) {
        images.push({
            src: link.href,
            thumb: link.querySelector("img")?.src || "",
            alt: link.dataset.title || "Фото из отзыва"
        });
    });

    function openLightbox(index) {
        if (index < 0) index = images.length - 1;
        if (index >= images.length) index = 0;
        currentIndex = index;

        lightboxImage.src = images[index].src;
        lightboxImage.alt = images[index].alt;
        updateCounter();
        renderThumbs();
        lightbox.classList.add("show");
        document.body.style.overflow = "hidden";
    }

    function closeLightbox() {
        lightbox.classList.remove("show");
        document.body.style.overflow = "";
    }

    function updateCounter() {
        lightboxCurrent.textContent = currentIndex + 1;
        lightboxTotal.textContent = images.length;
    }

    function renderThumbs() {
        lightboxThumbs.innerHTML = "";

        images.forEach(function(imgData, index) {
            const img = document.createElement("img");
            img.src = imgData.thumb;
            img.loading = "lazy";
            img.className = "lightbox-thumb";
            if (index === currentIndex) {
                img.classList.add("active");
            }

            img.addEventListener("click", function(e) {
                e.stopPropagation();
                currentIndex = index;
                lightboxImage.src = images[index].src;
                lightboxImage.alt = images[index].alt;
                updateCounter();
                renderThumbs();
            });

            lightboxThumbs.appendChild(img);
        });
    }

    // Открытие по клику на фото
    reviewLinks.forEach(function(link, index) {
        link.addEventListener("click", function(e) {
            e.preventDefault();
            openLightbox(index);
        });
    });

    // Закрытие
    lightboxClose.addEventListener("click", function(e) {
        e.stopPropagation();
        closeLightbox();
    });

    // Стрелки
    lightboxPrev.addEventListener("click", function(e) {
        e.stopPropagation();
        openLightbox(currentIndex - 1);
    });

    lightboxNext.addEventListener("click", function(e) {
        e.stopPropagation();
        openLightbox(currentIndex + 1);
    });

    // Закрытие по фону
    lightbox.addEventListener("click", function(e) {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });

    // Клавиши
    document.addEventListener("keydown", function(e) {
        if (lightbox.classList.contains("show")) {
            if (e.key === "Escape") {
                closeLightbox();
            } else if (e.key === "ArrowLeft") {
                openLightbox(currentIndex - 1);
            } else if (e.key === "ArrowRight") {
                openLightbox(currentIndex + 1);
            }
        }
    });

});