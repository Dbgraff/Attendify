import { api } from './api.js';
import { Utils } from './utils.js';
import { CalendarManager } from './calendar.js';
import { CardsManager } from './cards.js';
import { AttendanceManager } from './attendance.js';
import { StudentsManager } from './students.js';

export class AttendanceApp {
    constructor() {
        this.api = api;
        this.selectedGroup = null;
        this.students = [];
        this.calendar = new CalendarManager(this);
        this.cards = new CardsManager(this);
        this.attendance = new AttendanceManager(this);
        this.studentsManager = new StudentsManager(this);
        this.init();
    }

    async init() {
        await this.loadGroups();
        this.calendar.init();
        this.attachEventListeners();
        await this.refreshStudents();
        await this.refreshSchedule();
    }

    async loadGroups() {
        try {
            const groups = await this.api.getGroups();
            const select = document.getElementById('groupSelect');
            select.innerHTML = '<option value="">Выберите группу</option>';
            groups.forEach(group => {
                const option = document.createElement('option');
                option.value = group;
                option.textContent = group;
                select.appendChild(option);
            });
            // Загружаем последнюю выбранную группу из localStorage
            const lastGroup = localStorage.getItem('selectedGroup');
            if (lastGroup && groups.includes(lastGroup)) {
                select.value = lastGroup;
                this.selectedGroup = lastGroup;
            } else if (groups.length) {
                select.value = groups[0];
                this.selectedGroup = groups[0];
            }
            select.addEventListener('change', async (e) => {
                this.selectedGroup = e.target.value;
                localStorage.setItem('selectedGroup', this.selectedGroup);
                await this.refreshStudents();
                await this.refreshSchedule();
            });
        } catch (err) {
            console.error('Failed to load groups:', err);
            document.getElementById('groupSelect').innerHTML = '<option>Ошибка загрузки групп</option>';
        }
    }

    async refreshStudents() {
        if (!this.selectedGroup) {
            this.students = [];
            return;
        }
        try {
            this.students = await this.api.getStudents(this.selectedGroup);
            this.updateStats();
        } catch (err) {
            console.error('Failed to load students:', err);
            this.students = [];
        }
    }

    async refreshSchedule() {
        await this.cards.render();
        this.updateStats();
    }

    async updateStats() {
        if (!this.selectedGroup || !this.students.length) {
            document.getElementById('totalPresent').textContent = '0';
            document.getElementById('totalLate').textContent = '0';
            document.getElementById('totalExcused').textContent = '0';
            document.getElementById('totalAbsent').textContent = '0';
            return;
        }

        // Для статистики нужно собрать отметки за все занятия на выбранную дату?
        // Пока сделаем заглушку, можно посчитать по всем карточкам на текущую дату.
        // Упростим: считаем по всем занятиям текущего дня, но для удобства используем текущую дату.
        const date = this.calendar.getSelectedDate().toISOString().split('T')[0];
        const lessons = await this.api.getSchedule(this.selectedGroup, date);
        let present = 0, late = 0, excused = 0, absent = 0;
        for (const lesson of lessons) {
            const attendance = await this.api.getAttendance(lesson.id);
            present += attendance.filter(a => a.status === 'present').length;
            late += attendance.filter(a => a.status === 'late').length;
            excused += attendance.filter(a => a.status === 'excused').length;
            absent += attendance.filter(a => a.status === 'absent').length;
        }
        document.getElementById('totalPresent').textContent = present;
        document.getElementById('totalLate').textContent = late;
        document.getElementById('totalExcused').textContent = excused;
        document.getElementById('totalAbsent').textContent = absent;
    }

    attachEventListeners() {
        document.getElementById('groupBtn').addEventListener('click', () => {
            this.studentsManager.showModal();
        });
        document.getElementById('reportBtn').addEventListener('click', () => {
            this.showNotification('Функция отчётов в разработке', 'info');
        });
    }

    openAttendanceModal(lessonId, lesson) {
        this.attendance.showModal(lessonId, lesson);
    }

    showNotification(message, type = 'info') {
        // Простая реализация
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</div>
            <div class="notification-content">${message}</div>
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    }
}

// Запуск
window.addEventListener('DOMContentLoaded', () => {
    window.app = new AttendanceApp();
});