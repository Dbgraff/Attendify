export const Utils = {
    formatDate(date) {
        const options = { weekday: 'long', day: 'numeric', month: 'long' };
        return date.toLocaleDateString('ru-RU', options);
    },
    formatTime(date) {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    },
    getPlural(n, titles) {
        const cases = [2, 0, 1, 1, 1, 2];
        return titles[(n % 100 > 4 && n % 100 < 20) ? 2 : cases[(n % 10 < 5) ? n % 10 : 5]];
    },
    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
};