import { Utils } from './utils.js';

export class AttendanceManager {
    constructor(app) {
        this.app = app;
        this.currentLessonId = null;
        this.currentLesson = null;
    }

    async showModal(lessonId, lesson) {
        this.currentLessonId = lessonId;
        this.currentLesson = lesson;

        // Загружаем студентов и текущие отметки
        const students = this.app.students;
        const attendance = await this.app.api.getAttendance(lessonId);

        // Создаём HTML модалки
        const modalHtml = `
            <div class="modal-overlay" id="attendanceModal">
                <div class="modal">
                    <div class="modal-header">
                        <h2 class="modal-title">${Utils.escapeHtml(lesson.discipline)}</h2>
                        <button class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="lesson-info">
                            <div><i class="fas fa-user-tie"></i> ${Utils.escapeHtml(lesson.teacher)}</div>
                            <div><i class="fas fa-map-marker-alt"></i> ${Utils.escapeHtml(lesson.room)}</div>
                            <div><i class="far fa-clock"></i> ${Utils.escapeHtml(lesson.time || '')}</div>
                        </div>

                        <div class="attendance-stats" id="modalStats"></div>

                        <div class="students-list" id="studentsList"></div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="closeModalBtn">Закрыть</button>
                    </div>
                </div>
            </div>
        `;

        const container = document.getElementById('modalsContainer');
        container.innerHTML = modalHtml;

        const modal = document.getElementById('attendanceModal');
        const closeBtn = modal.querySelector('.modal-close');
        const closeModalBtn = document.getElementById('closeModalBtn');

        const closeModal = () => {
            modal.remove();
            this.currentLessonId = null;
            this.currentLesson = null;
        };

        closeBtn.addEventListener('click', closeModal);
        closeModalBtn.addEventListener('click', closeModal);

        // Рендерим статистику и список студентов
        await this.renderAttendanceStats(attendance, students);
        await this.renderStudentList(students, attendance);

        // Обработчики для кнопок статусов
        modal.addEventListener('click', async (e) => {
            const btn = e.target.closest('.status-btn');
            if (!btn) return;

            const studentId = btn.dataset.studentId;
            const status = btn.dataset.status;
            const currentStatus = attendance.find(a => a.student_id == studentId)?.status;

            // Если уже выбран этот статус — сбрасываем (null)
            const newStatus = (currentStatus === status) ? null : status;

            try {
                await this.app.api.setAttendance(this.currentLessonId, studentId, newStatus);
                // Обновляем данные и перерисовываем
                const newAttendance = await this.app.api.getAttendance(this.currentLessonId);
                await this.renderAttendanceStats(newAttendance, students);
                await this.renderStudentList(students, newAttendance);
                // Обновляем карточку на главной
                this.app.refreshSchedule();
            } catch (err) {
                console.error('Error saving attendance:', err);
                this.app.showNotification('Ошибка сохранения', 'error');
            }
        });
    }

    async renderAttendanceStats(attendance, students) {
        const stats = {
            present: attendance.filter(a => a.status === 'present').length,
            late: attendance.filter(a => a.status === 'late').length,
            excused: attendance.filter(a => a.status === 'excused').length,
            absent: attendance.filter(a => a.status === 'absent').length
        };
        const total = students.length;
        const statsHtml = `
            <div class="stat-item"><span class="stat-value present">${stats.present}</span><span>✅ Присутствуют</span></div>
            <div class="stat-item"><span class="stat-value late">${stats.late}</span><span>⏰ Опоздали</span></div>
            <div class="stat-item"><span class="stat-value excused">${stats.excused}</span><span>🏥 По уважительной</span></div>
            <div class="stat-item"><span class="stat-value absent">${stats.absent}</span><span>❌ Отсутствуют</span></div>
            <div class="stat-item"><span class="stat-value">${total}</span><span>👥 Всего</span></div>
        `;
        document.getElementById('modalStats').innerHTML = statsHtml;
    }

    async renderStudentList(students, attendance) {
        const container = document.getElementById('studentsList');
        if (!container) return;

        if (!students.length) {
            container.innerHTML = '<p class="empty-state">Нет студентов в группе</p>';
            return;
        }

        container.innerHTML = '';
        for (const student of students) {
            const record = attendance.find(a => a.student_id == student.id);
            const status = record?.status || null;

            const row = document.createElement('div');
            row.className = 'student-row';
            row.innerHTML = `
                <div class="student-name">${Utils.escapeHtml(student.full_name)}</div>
                <div class="attendance-buttons">
                    <button class="status-btn ${status === 'present' ? 'active' : ''}" data-student-id="${student.id}" data-status="present">✅</button>
                    <button class="status-btn ${status === 'late' ? 'active' : ''}" data-student-id="${student.id}" data-status="late">⏰</button>
                    <button class="status-btn ${status === 'excused' ? 'active' : ''}" data-student-id="${student.id}" data-status="excused">🏥</button>
                    <button class="status-btn ${status === 'absent' ? 'active' : ''}" data-student-id="${student.id}" data-status="absent">❌</button>
                </div>
            `;
            container.appendChild(row);
        }
    }
}