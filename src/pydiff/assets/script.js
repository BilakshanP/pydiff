(function() {
    function setView(split, mode) {
        var L = split.querySelector('.pane.left');
        var R = split.querySelector('.pane.right');
        var H = split.querySelector('.handle');
        L.classList.remove('hidden','solo'); R.classList.remove('hidden','solo'); H.classList.remove('hidden');
        if (mode === 'left')  { R.classList.add('hidden'); H.classList.add('hidden'); L.classList.add('solo'); }
        if (mode === 'right') { L.classList.add('hidden'); H.classList.add('hidden'); R.classList.add('solo'); }
        if (mode === 'both') { L.style.flexBasis = '50%'; R.style.flexBasis = '50%'; }
        split.dataset.view = mode;
        var fc = split.closest('.file-content');
        fc.querySelectorAll('[data-view]').forEach(function(b) {
            b.classList.toggle('active', b.dataset.view === mode);
        });
    }

    // Measure each table's sticky header once and set scroll-padding-top on
    // its scroll ancestors so f/n/t anchor jumps land below the header.
    function applyScrollPadding() {
        document.querySelectorAll('.file-content').forEach(function(fc) {
            var th = fc.querySelector('table.diff thead th');
            if (!th) return;
            var pad = th.getBoundingClientRect().height + 4;
            fc.querySelectorAll('.split, .pane').forEach(function(s) {
                s.style.scrollPaddingTop = pad + 'px';
            });
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyScrollPadding);
    } else {
        applyScrollPadding();
    }

    document.querySelectorAll('.file-content').forEach(function(fc) {
        var split = fc.querySelector('.split:not(.single)');
        if (!split) return;
        var L = split.querySelector('.pane.left');
        var R = split.querySelector('.pane.right');
        var H = split.querySelector('.handle');

        fc.querySelectorAll('[data-view]').forEach(function(b) {
            b.addEventListener('click', function(e) {
                e.preventDefault();
                setView(split, b.dataset.view);
            });
        });
        var syncBtn = fc.querySelector('[data-sync-toggle]');
        if (syncBtn) {
            syncBtn.addEventListener('click', function(e) {
                e.preventDefault();
                var wasSync = !split.classList.contains('nosync');
                var y = wasSync ? split.scrollTop : (L.scrollTop || R.scrollTop);
                split.classList.toggle('nosync');
                var on = !split.classList.contains('nosync');
                syncBtn.classList.toggle('active', on);
                syncBtn.textContent = on ? 'Sync: on' : 'Sync: off';
                // Transfer scroll position to the newly-active scroller(s).
                requestAnimationFrame(function() {
                    if (on) {
                        split.scrollTop = y;
                    } else {
                        L.scrollTop = y;
                        R.scrollTop = y;
                    }
                });
            });
        }

        // Drag handle
        var dragging = false;
        H.addEventListener('mousedown', function(e) {
            if (split.dataset.view !== 'both') return;
            dragging = true;
            H.classList.add('dragging');
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            var rect = split.getBoundingClientRect();
            var pct = ((e.clientX - rect.left) / rect.width) * 100;
            pct = Math.max(10, Math.min(90, pct));
            L.style.flexBasis = pct + '%';
            R.style.flexBasis = (100 - pct) + '%';
        });
        document.addEventListener('mouseup', function() {
            if (dragging) { dragging = false; H.classList.remove('dragging'); }
        });
    });

    // In-pane f/n/t nav links. Intercept clicks so the browser scrolls the
    // diff container rather than the page.
    document.querySelectorAll('table.diff td.diff_next a').forEach(function(a) {
        a.addEventListener('click', function(e) {
            var href = a.getAttribute('href') || '';
            if (href.charAt(0) !== '#') return;
            var target = document.getElementById(href.slice(1));
            if (!target) return;
            e.preventDefault();
            // `t` target is the <table> itself — just scroll its container to 0
            // so the header lands at its natural position (avoids the
            // scroll-padding-top adding extra gap above it).
            if (target.tagName === 'TABLE') {
                var scroller = target.closest('.split:not(.nosync)')
                    || target.closest('.pane');
                if (scroller) { scroller.scrollTop = 0; return; }
            }
            target.scrollIntoView({ block: 'start', inline: 'nearest' });
        });
    });

    // Target prev/next navigation
    var targets = Array.prototype.slice.call(document.querySelectorAll('.target-section'));
    if (targets.length > 1) {
        var prev = document.getElementById('nav-prev');
        var next = document.getElementById('nav-next');
        function currentIndex() {
            var y = window.scrollY + 80;
            var idx = 0;
            for (var i = 0; i < targets.length; i++) {
                if (targets[i].offsetTop <= y) idx = i;
            }
            return idx;
        }
        function jump(delta) {
            var i = currentIndex() + delta;
            if (i < 0) i = 0;
            if (i >= targets.length) i = targets.length - 1;
            targets[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        if (prev) prev.addEventListener('click', function() { jump(-1); });
        if (next) next.addEventListener('click', function() { jump(1); });
    }

    // Fullscreen toggle (target-section or file-container)
    var fsCurrent = null;
    function exitFullscreen() {
        if (!fsCurrent) return;
        fsCurrent.classList.remove('fullscreen');
        var btn = fsCurrent.querySelector(':scope > summary [data-expand]');
        if (btn) btn.textContent = '⛶';
        fsCurrent = null;
        document.body.classList.remove('has-fullscreen');
    }
    document.querySelectorAll('[data-expand]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            var container = btn.closest('.file-container') || btn.closest('.target-section');
            if (!container) return;
            if (fsCurrent === container) { exitFullscreen(); return; }
            if (fsCurrent) exitFullscreen();
            container.classList.add('fullscreen');
            if (!container.open) container.open = true;
            btn.textContent = '✕';
            fsCurrent = container;
            document.body.classList.add('has-fullscreen');
            // Measure file-header height so CSS can size .file-content to fill the rest.
            if (container.classList.contains('file-container')) {
                var hdr = container.querySelector(':scope > .file-header');
                if (hdr) container.style.setProperty('--fs-header-h', hdr.offsetHeight + 'px');
            }
        });
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') exitFullscreen();
    });

    // File prev/next navigation in fullscreen
    function fsNavigate(delta) {
        if (!fsCurrent || !fsCurrent.classList.contains('file-container')) return;
        var siblings = Array.prototype.slice.call(
            fsCurrent.parentElement.querySelectorAll(':scope > .file-container')
        );
        var idx = siblings.indexOf(fsCurrent) + delta;
        if (idx < 0 || idx >= siblings.length) return;
        var target = siblings[idx];
        exitFullscreen();
        // Enter fullscreen on the target
        target.classList.add('fullscreen');
        if (!target.open) target.open = true;
        var btn = target.querySelector(':scope > summary [data-expand]');
        if (btn) btn.textContent = '✕';
        fsCurrent = target;
        document.body.classList.add('has-fullscreen');
        var hdr = target.querySelector(':scope > .file-header');
        if (hdr) target.style.setProperty('--fs-header-h', hdr.offsetHeight + 'px');
    }
    document.querySelectorAll('[data-fs-prev]').forEach(function(b) {
        b.addEventListener('click', function(e) { e.preventDefault(); e.stopPropagation(); fsNavigate(-1); });
    });
    document.querySelectorAll('[data-fs-next]').forEach(function(b) {
        b.addEventListener('click', function(e) { e.preventDefault(); e.stopPropagation(); fsNavigate(1); });
    });

    // Walk mode: step navigation
    if (typeof walkSteps !== 'undefined' && walkSteps.length) {
        var walkIdx = 0;
        var steps = document.querySelectorAll('.walk-step');
        var info = document.getElementById('walk-info');
        var wp = document.getElementById('walk-prev');
        var wn = document.getElementById('walk-next');
        function walkUpdate() {
            steps.forEach(function(s, i) { s.style.display = i === walkIdx ? '' : 'none'; });
            var s = walkSteps[walkIdx];
            if (info) info.innerHTML = '<strong>' + s.hash + '</strong> ' + s.subject +
                ' <span style="color:#6e7781">— ' + s.author + ', ' + s.date + '</span>' +
                ' <span style="color:#8b949e">(' + (walkIdx + 1) + ' / ' + walkSteps.length + ')</span>';
            if (wp) wp.disabled = walkIdx === 0;
            if (wn) wn.disabled = walkIdx === steps.length - 1;
            window.scrollTo(0, 0);
        }
        if (wp) wp.addEventListener('click', function() { if (walkIdx > 0) { walkIdx--; walkUpdate(); } });
        if (wn) wn.addEventListener('click', function() { if (walkIdx < steps.length - 1) { walkIdx++; walkUpdate(); } });
        walkUpdate();
    }
})();
