import { Utils } from './utils.js';

export class CardsManager {
    constructor(app) {
        this.app = app;
    }

    async render() {
        const container = document.getElementById('cardsContainer');
        const emptyState = document.getElementById('emptyState');
        const cardsCountSpan = document.getElementById('cardsCount');

        const group = this.app.selectedGroup;
        const date = this.app.calendar.getSelectedDate();
        const dateStr = date.toISOString().split('T')[0];

        if (!group) {
            // Если группы нет, показываем emptyState
            if (emptyState) emptyState.style.display = 'flex';
            // Очищаем все карточки, но сохраняем emptyState
            Array.from(container.children).forEach(child => {
                if (child !== emptyState) child.remove();
            });
            if (cardsCountSpan) cardsCountSpan.textContent = '0 пар';
            return;
        }

        try {
            const lessons = await this.app.api.getSchedule(group, dateStr);
            if (cardsCountSpan) cardsCountSpan.textContent = `${lessons.length} ${Utils.getPlural(lessons.length, ['пара', 'пары', 'пар'])}`;

            if (lessons.length === 0) {
                if (emptyState) emptyState.style.display = 'flex';
                // Удаляем все лишние элементы, кроме emptyState
                Array.from(container.children).forEach(child => {
                    if (child !== emptyState) child.remove();
                });
                return;
            }

            // Скрываем emptyState
            if (emptyState) emptyState.style.display = 'none';

            // Удаляем все элементы, кроме emptyState
            Array.from(container.children).forEach(child => {
                if (child !== emptyState) child.remove();
            });

            // Добавляем карточки
            for (const lesson of lessons) {
                const attendance = await this.app.api.getAttendance(lesson.id);
                const students = this.app.students;
                const total = students.length;
                const presentCount = attendance.filter(a => a.status === 'present').length;
                const percent = total ? Math.round(presentCount / total * 100) : 0;
                let attendanceClass = '';
                if (percent >= 80) attendanceClass = 'attendance-good';
                else if (percent >= 50) attendanceClass = 'attendance-medium';
                else if (percent > 0) attendanceClass = 'attendance-poor';

                const card = document.createElement('div');
                card.className = 'card';
                card.dataset.id = lesson.id;
                card.innerHTML = `
                <div class="card-header">
                    <div class="card-title">${Utils.escapeHtml(lesson.discipline)}</div>
                    <div class="card-time"><i class="far fa-clock"></i> ${Utils.escapeHtml(lesson.time || '')}</div>
                </div>
                <div class="card-details">
                    <div class="card-detail"><i class="fas fa-user-tie"></i> ${Utils.escapeHtml(lesson.teacher)}</div>
                    <div class="card-detail"><i class="fas fa-map-marker-alt"></i> ${Utils.escapeHtml(lesson.room)}</div>
                </div>
                ${total ? `
                <div class="card-attendance ${attendanceClass}">
                    <span class="attendance-count">${presentCount}/${total}</span>
                    <span>присутствуют (${percent}%)</span>
                </div>
                ` : ''}
            `;
                card.addEventListener('click', () => this.app.openAttendanceModal(lesson.id, lesson));
                container.appendChild(card);
            }
        } catch (err) {
            console.error('Error loading schedule:', err);
            container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>Ошибка загрузки расписания</p></div>';
        }
    }
}