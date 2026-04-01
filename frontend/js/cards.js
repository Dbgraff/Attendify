// cards.js
import { Utils } from './utils.js';

export class CardsManager {
    constructor(app) {
        this.app = app;
    }

    async render() {
        const container = document.getElementById('cardsContainer');
        const emptyState = document.getElementById('emptyState');
        const cardsCountSpan = document.getElementById('cardsCount');

        const selectedGroup = this.app.selectedGroup; // может быть '' (все пары)
        const date = this.app.calendar.getSelectedDate();
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const dateStr = `${year}-${month}-${day}`;

        try {
            // Запрос расписания с учётом выбранной группы
            const lessons = await this.app.api.getSchedule(selectedGroup, dateStr);

            // Обновляем счётчик пар
            if (cardsCountSpan) {
                cardsCountSpan.textContent = `${lessons.length} ${Utils.getPlural(lessons.length, ['пара', 'пары', 'пар'])}`;
            }

            // Обработка пустого расписания
            if (lessons.length === 0) {
                if (emptyState) emptyState.style.display = 'flex';
                // Удаляем все карточки, кроме emptyState
                Array.from(container.children).forEach(child => {
                    if (child !== emptyState) child.remove();
                });
                return;
            }

            // Если есть занятия, скрываем emptyState и очищаем контейнер
            if (emptyState) emptyState.style.display = 'none';
            Array.from(container.children).forEach(child => {
                if (child !== emptyState) child.remove();
            });

            // Получаем студентов только для выбранной группы (если группа выбрана)
            // Если выбраны все пары, students = [], статистика в карточках не показывается
            const students = this.app.students;

            for (const lesson of lessons) {
                const attendance = await this.app.api.getAttendance(lesson.id);
                let filteredStudents = students;

                // Фильтруем студентов по подгруппе, если есть студенты и подгруппа занятия задана
                if (students.length > 0) {
                    if (lesson.podgr === 1) {
                        filteredStudents = students.filter(s => s.subgroup === 1);
                    } else if (lesson.podgr === 2) {
                        filteredStudents = students.filter(s => s.subgroup === 2);
                    }
                }

                const total = filteredStudents.length;
                const presentCount = attendance.filter(a => {
                    const student = filteredStudents.find(s => s.id === a.student_id);
                    return student && a.status === 'present';
                }).length;
                const percent = total ? Math.round(presentCount / total * 100) : 0;
                let attendanceClass = '';
                if (percent >= 80) attendanceClass = 'attendance-good';
                else if (percent >= 50) attendanceClass = 'attendance-medium';
                else if (percent > 0) attendanceClass = 'attendance-poor';

                // Если выбраны все пары и в занятии есть код группы, показываем его
                let groupHtml = '';
                if (!selectedGroup && lesson.group_code) {
                    groupHtml = `<div class="card-detail"><i class="fas fa-users"></i> Группа: ${Utils.escapeHtml(lesson.group_code)}</div>`;
                }

                const card = document.createElement('div');
                card.className = 'card';
                card.dataset.id = lesson.id;
                const paraText = lesson.para ? `${lesson.para} пара` : '';
                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-title">${Utils.escapeHtml(lesson.discipline)}</div>
                        <div class="card-time">
                            ${paraText ? `<span class="card-para">${paraText}</span>` : ''}
                            ${lesson.time ? `<i class="far fa-clock"></i> ${Utils.escapeHtml(lesson.time)}` : ''}
                        </div>
                    </div>
                    <div class="card-details">
                        <div class="card-detail"><i class="fas fa-user-tie"></i> ${Utils.escapeHtml(lesson.teacher)}</div>
                        <div class="card-detail"><i class="fas fa-map-marker-alt"></i> ${Utils.escapeHtml(lesson.room)}</div>
                        ${groupHtml}
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