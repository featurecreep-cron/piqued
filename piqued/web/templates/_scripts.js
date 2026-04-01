// CSRF token from meta tag
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

// Keyboard navigation
let currentIdx = -1;
const cards = () => [...document.querySelectorAll('.section-card')];

document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    const c = cards();
    if (!c.length) return;
    if (e.key === 'j') { currentIdx = Math.min(currentIdx + 1, c.length - 1); c[currentIdx].focus(); c[currentIdx].scrollIntoView({block: 'nearest'}); }
    if (e.key === 'k') { currentIdx = Math.max(currentIdx - 1, 0); c[currentIdx].focus(); c[currentIdx].scrollIntoView({block: 'nearest'}); }
    if (e.key === 'u' && currentIdx >= 0) { c[currentIdx].querySelector('.feedback-btns button:first-child')?.click(); }
    if (e.key === 'd' && currentIdx >= 0) { c[currentIdx].querySelector('.feedback-btns button:last-child')?.click(); }
    if (e.key === 'Enter' && currentIdx >= 0) { e.preventDefault(); c[currentIdx].classList.toggle('collapsed'); }
});

function toggleCollapse(header) {
    header.closest('.section-card').classList.toggle('collapsed');
}

async function vote(sectionId, rating, btn) {
    const card = btn.closest('.section-card');
    const btns = card.querySelectorAll('.feedback-btns button');

    if (rating < 0) {
        // Show detailed feedback panel on thumbs-down
        btns.forEach(b => b.classList.remove('voted-up', 'voted-down'));
        btn.classList.add('voted-down');
        const detail = card.querySelector('.feedback-detail');
        if (detail) {
            detail.style.display = detail.style.display === 'none' ? 'block' : 'none';
        }
        // Also send the basic -1 immediately (reason can follow)
        fetch('/api/feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
            body: JSON.stringify({section_id: sectionId, rating: -1, source: 'explicit'})
        }).catch(() => {});
        return;
    }

    // Thumbs up — immediate
    try {
        const resp = await fetch('/api/feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
            body: JSON.stringify({section_id: sectionId, rating: 1, source: 'explicit'})
        });
        const data = await resp.json();
        if (data.ok) {
            btns.forEach(b => b.classList.remove('voted-up', 'voted-down'));
            btn.classList.add('voted-up');
            // Hide any open feedback detail panel
            const detail = card.querySelector('.feedback-detail');
            if (detail) detail.style.display = 'none';
            let msg = card.querySelector('.feedback-msg');
            if (!msg) { msg = document.createElement('div'); msg.className = 'feedback-msg'; card.querySelector('.section-body').appendChild(msg); }
            msg.textContent = `Got it — similar sections will rank ${data.direction}`;
        }
    } catch (e) { console.error('Feedback failed:', e); }
}

function selectReason(chip) {
    chip.classList.toggle('selected');
}

async function submitDetailedFeedback(sectionId, btn) {
    const card = btn.closest('.section-card');
    const chips = card.querySelectorAll('.chip.selected');
    const textInput = card.querySelector('.feedback-reason-text');
    const reasons = [...chips].map(c => c.textContent);
    if (textInput && textInput.value.trim()) reasons.push(textInput.value.trim());

    const reason = reasons.join('; ') || null;

    try {
        await fetch('/api/feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
            body: JSON.stringify({section_id: sectionId, rating: -1, source: 'explicit', reason: reason})
        });

        // Collapse the panel and show confirmation
        const detail = card.querySelector('.feedback-detail');
        if (detail) detail.style.display = 'none';
        let msg = card.querySelector('.feedback-msg');
        if (!msg) { msg = document.createElement('div'); msg.className = 'feedback-msg'; card.querySelector('.section-body').appendChild(msg); }
        msg.textContent = reason ? `Got it: "${reason}" — adjusting` : 'Got it — similar sections will rank lower';
    } catch (e) { console.error('Detailed feedback failed:', e); }
}

async function trackClick(sectionId) {
    fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
        body: JSON.stringify({section_id: sectionId, rating: 1, source: 'click_through'})
    }).catch(() => {});
}

async function downweight(tag) {
    try {
        const resp = await fetch('/api/downweight', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken},
            body: JSON.stringify({tag: tag})
        });
        const data = await resp.json();
        if (data.ok) {
            // Visual feedback — find all instances of this tag and dim them
            document.querySelectorAll('.tag-weight').forEach(el => {
                if (el.textContent.includes(tag)) {
                    el.style.opacity = '0.4';
                    el.querySelector('small').textContent = `(${data.new_weight.toFixed(1)})`;
                }
            });
        }
    } catch (e) { console.error('Downweight failed:', e); }
}
