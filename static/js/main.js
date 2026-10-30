/**
 * PetCare – Main JavaScript
 * Handles: mobile nav, date validation, form submit loading state,
 *          confirm dialogs, flash auto-dismiss, status badges,
 *          URL query pre-select, animated number counters,
 *          portal sidebar toggle, and smooth scroll reveal animations.
 */

document.addEventListener('DOMContentLoaded', () => {

  /* ── MOBILE SITE NAVIGATION ───────────────────────────────────────── */
  const menuToggle = document.getElementById('menuToggle');
  const mainNav    = document.getElementById('mainNav');

  if (menuToggle && mainNav) {
    menuToggle.addEventListener('click', () => {
      const isOpen = mainNav.classList.toggle('open');
      menuToggle.classList.toggle('open', isOpen);
      menuToggle.setAttribute('aria-expanded', String(isOpen));
      menuToggle.setAttribute('aria-label', isOpen ? 'Đóng menu' : 'Mở menu');
    });

    // Close nav when a link is clicked
    mainNav.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        mainNav.classList.remove('open');
        menuToggle.classList.remove('open');
        menuToggle.setAttribute('aria-expanded', 'false');
        menuToggle.setAttribute('aria-label', 'Mở menu');
      });
    });

    // Close nav when clicking outside
    document.addEventListener('click', (e) => {
      if (!menuToggle.contains(e.target) && !mainNav.contains(e.target)) {
        mainNav.classList.remove('open');
        menuToggle.classList.remove('open');
        menuToggle.setAttribute('aria-expanded', 'false');
        menuToggle.setAttribute('aria-label', 'Mở menu');
      }
    });
  }

  /* ── PORTAL SIDEBAR TOGGLE (FOR MOBILE / TABLET) ─────────────────── */
  const portalToggle  = document.getElementById('portalSidebarToggle');
  const portalSidebar = document.getElementById('portalSidebar');

  if (portalToggle && portalSidebar) {
    portalToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      portalSidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (portalSidebar.classList.contains('open') && !portalSidebar.contains(e.target) && !portalToggle.contains(e.target)) {
        portalSidebar.classList.remove('open');
      }
    });
  }

  /* ── DATE INPUT: Form đặt lịch của khách hàng ────────────────────── */
  const clientBookingDate = document.querySelector('#bookingForm #appointmentDate');
  if (clientBookingDate) {
    const now = new Date();
    const localToday = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString().slice(0, 10);
    clientBookingDate.min = localToday;
    clientBookingDate.addEventListener('change', () => {
      if (clientBookingDate.value && clientBookingDate.value < localToday) {
        clientBookingDate.value = '';
        clientBookingDate.setCustomValidity('Vui lòng chọn ngày từ hôm nay trở đi.');
        clientBookingDate.reportValidity();
      } else {
        clientBookingDate.setCustomValidity('');
      }
    });
  }

  /* ── FORM: Ngăn double-submit chỉ khi form đã pass validation ────── */
  const bookingForm = document.getElementById('bookingForm');
  if (bookingForm) {
    bookingForm.addEventListener('submit', function (event) {
      if (!bookingForm.checkValidity()) {
        return; // Để trình duyệt hiển thị tooltip validation
      }
      const btn     = this.querySelector('#submitBtn');
      const btnText = this.querySelector('.btn-text');
      const btnLoad = this.querySelector('.btn-loading');
      if (btn) {
        btn.disabled = true;
        if (btnText) btnText.hidden = true;
        if (btnLoad) btnLoad.hidden = false;
      }
    });
  }

  /* ── CONFIRM BEFORE DELETE / DESTRUCTIVE ACTION ───────────────────── */
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      const msg = form.dataset.confirm || 'Bạn có chắc chắn thực hiện thao tác này không?';
      if (!window.confirm(msg)) {
        event.preventDefault();
      }
    });
  });

  /* ── STATUS BADGE: apply CSS class based on text content ─────────── */
  document.querySelectorAll('.status').forEach(badge => {
    const text = badge.textContent.trim();
    if (text === 'Đã xác nhận')  badge.classList.add('status-da-xac-nhan');
    if (text === 'Đã hoàn thành') badge.classList.add('status-da-hoan-thanh');
    if (text === 'Đã hủy')       badge.classList.add('status-da-huy');
  });

  /* ── FLASH AUTO-DISMISS ───────────────────────────────────────────── */
  document.querySelectorAll('.flash').forEach(flash => {
    const delay = flash.classList.contains('error') ? 9000 : 6500;
    setTimeout(() => {
      if (flash.isConnected) flash.classList.add('flash-fade');
      setTimeout(() => { if (flash.isConnected) flash.remove(); }, 350);
    }, delay);
  });

  /* ── PRE-SELECT SERVICE FROM URL PARAM ────────────────────────────── */
  const serviceSelect = document.getElementById('serviceSelect');
  if (serviceSelect) {
    const params = new URLSearchParams(window.location.search);
    const svc = params.get('service');
    if (svc) {
      for (const opt of serviceSelect.options) {
        if (opt.value === svc || opt.textContent.includes(svc)) {
          opt.selected = true;
          break;
        }
      }
    }
  }

  /* ── ANIMATED NUMBER COUNTERS ─────────────────────────────────────── */
  const counterElements = document.querySelectorAll('.counter');
  if (counterElements.length > 0 && 'IntersectionObserver' in window) {
    const counterObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseFloat(el.getAttribute('data-target') || el.innerText.replace(/[^0-9.]/g, ''));
          if (!isNaN(target) && target > 0) {
            let start = 0;
            const duration = 1600; // ms
            const startTime = performance.now();
            const originalText = el.innerText;
            const hasPlus = originalText.includes('+');
            const hasPercent = originalText.includes('%');
            
            function updateCounter(currentTime) {
              const elapsed = currentTime - startTime;
              const progress = Math.min(elapsed / duration, 1);
              // Ease-out cubic
              const ease = 1 - Math.pow(1 - progress, 3);
              const currentVal = Math.floor(start + (target - start) * ease);
              
              let formatted = currentVal >= 1000 ? currentVal.toLocaleString('vi-VN') : currentVal;
              if (hasPercent && progress >= 1 && target % 1 !== 0) {
                formatted = target.toFixed(1);
              }
              if (hasPlus) formatted += '+';
              if (hasPercent) formatted += '%';
              
              el.innerText = formatted;
              if (progress < 1) {
                requestAnimationFrame(updateCounter);
              } else {
                el.innerText = originalText;
              }
            }
            requestAnimationFrame(updateCounter);
          }
          observer.unobserve(el);
        }
      });
    }, { threshold: 0.2 });

    counterElements.forEach(el => counterObserver.observe(el));
  }

  /* ── SCROLL REVEAL ANIMATIONS ──────────────────────────────────────── */
  const animTargets = document.querySelectorAll(
    '.service-card, .service-card-modern, .doctor-card, .doctor-home-card, .doctor-card-horizontal, .step-card, .process-step, .why-card, .review-box, .review-card, .mvv-card, .stat-block, .stat-block-modern, .facility-card, .standard-item'
  );

  if ('IntersectionObserver' in window && animTargets.length > 0) {
    const revealObserver = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal-in');
          obs.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.12,
      rootMargin: '0px 0px -30px 0px'
    });

    animTargets.forEach(el => {
      el.classList.add('reveal-init');
      revealObserver.observe(el);
    });
  }

});
