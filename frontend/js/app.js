import { api } from './api.js';
import { Utils } from './utils.js';
import { CalendarManager } from './calendar.js';
import { CardsManager } from './cards.js';
import { AttendanceManager } from './attendance.js';
import { StudentsManager } from './students.js';
import { UsersManager } from './users.js';

window.addEventListener('unhandledrejection', (event) => {
    console.error('Необработанное отклонение промиса:', event.reason);
    event.preventDefault(); // предотвращает возможную перезагрузку
});

export class AttendanceApp {
    constructor() {
        this.api = api;
        this.user = null;
        this.selectedGroup = null;
        this.students = [];
        this.calendar = new CalendarManager(this);
        this.cards = new CardsManager(this);
        this.attendance = new AttendanceManager(this);
        this.studentsManager = new StudentsManager(this);
        this.usersManager = new UsersManager(this);
        this.init();
    }

    async init() {

        window.addEventListener('beforeunload', () => {
            console.warn('[App] Page is about to unload');
            // можно добавить стек вызовов, но beforeunload не даёт сохранить много данных
        })
        const token = localStorage.getItem('access_token');
        if (token) {
            try {
                this.user = await this.api.me();
                await this.loadGroups();
                this.calendar.init();
                this.attachEventListeners();
                await this.refreshStudents();
                await this.refreshSchedule();
            } catch (err) {
                console.error('Auth error', err);
                this.showLogin();
            }
        } else {
            this.showLogin();
        }


    }

    showLogin() {
        const modalHtml = `
            <div class="modal-overlay" id="loginModal">
                <div class="modal">
                    <div class="modal-header">
                        <h2>Вход в Attendify</h2>
                    </div>
                    <div class="modal-body">
                        <input type="text" id="loginUsername" placeholder="Имя пользователя" class="form-control">
                        <input type="password" id="loginPassword" placeholder="Пароль" class="form-control" style="margin-top: 8px;">
                        <button id="loginSubmit" class="btn btn-primary" style="margin-top: 16px;">Войти</button>
                        <div id="loginError" style="color: red; margin-top: 8px;"></div>
                    </div>
                </div>
            </div>
        `;
        const container = document.getElementById('modalsContainer');
        container.innerHTML = modalHtml;
        document.getElementById('loginSubmit').addEventListener('click', async () => {
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            try {
                const data = await this.api.login(username, password);
                this.user = await this.api.me();
                container.innerHTML = '';
                await this.init();
            } catch (err) {
                document.getElementById('loginError').textContent = 'Неверное имя или пароль';
            }
        });
    }

    async loadGroups() {
        try {
            const groupsData = await this.api.getGroups(); // [{code, is_curator}]
            const select = document.getElementById('groupSelect');
            // Для админа не добавляем опцию "Все пары"
            if (this.user.role !== 'admin') {
                select.innerHTML = '<option value="">Все пары</option>';
            } else {
                select.innerHTML = '';
            }
            groupsData.forEach(group => {
                const option = document.createElement('option');
                option.value = group.code;
                if (this.user && this.user.role === 'curator' && group.is_curator) {
                    option.textContent = `🏛️ ${group.code} (кураторская)`;
                } else {
                    option.textContent = group.code;
                }
                select.appendChild(option);
            });

            // Выбор группы по умолчанию
            const lastGroup = localStorage.getItem('selectedGroup');
            if (lastGroup && groupsData.some(g => g.code === lastGroup)) {
                select.value = lastGroup;
                this.selectedGroup = lastGroup;
            } else if (groupsData.length) {
                // Если есть группы, выбираем первую
                select.value = groupsData[0].code;
                this.selectedGroup = groupsData[0].code;
            } else {
                // Групп нет
                select.value = '';
                this.selectedGroup = '';
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
            document.getElementById('totalPresent').textContent = '0';
            document.getElementById('totalLate').textContent = '0';
            document.getElementById('totalExcused').textContent = '0';
            document.getElementById('totalAbsent').textContent = '0';
            return;
        }
        try {
            this.students = await this.api.getStudents(this.selectedGroup);
            try {
                await this.updateStats();   // <-- добавлен await
            } catch (statsErr) {
                console.error('Ошибка при обновлении статистики:', statsErr);
                document.getElementById('totalPresent').textContent = '0';
                document.getElementById('totalLate').textContent = '0';
                document.getElementById('totalExcused').textContent = '0';
                document.getElementById('totalAbsent').textContent = '0';
            }
        } catch (err) {
            console.error('Не удалось загрузить студентов:', err);
            this.students = [];
        }
    }

    async refreshSchedule() {
        await this.cards.render();
        if (this.selectedGroup) {
            try {
                await this.updateStats();
            } catch (err) {
                console.error('Error updating stats in refreshSchedule:', err);
                // Сброс статистики
                document.getElementById('totalPresent').textContent = '0';
                document.getElementById('totalLate').textContent = '0';
                document.getElementById('totalExcused').textContent = '0';
                document.getElementById('totalAbsent').textContent = '0';
            }
        } else {
            document.getElementById('totalPresent').textContent = '—';
            document.getElementById('totalLate').textContent = '—';
            document.getElementById('totalExcused').textContent = '—';
            document.getElementById('totalAbsent').textContent = '—';
        }
    }

    async updateStats() {
        if (!this.selectedGroup || !this.students.length) {
            document.getElementById('totalPresent').textContent = '0';
            document.getElementById('totalLate').textContent = '0';
            document.getElementById('totalExcused').textContent = '0';
            document.getElementById('totalAbsent').textContent = '0';
            return;
        }

        const date = this.calendar.getSelectedDate();
        const dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

        try {
            const lessons = await this.api.getSchedule(this.selectedGroup, dateStr);
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
        } catch (err) {
            console.error('Error updating stats:', err);
            throw err; // Можно пробросить, если нужно обработать выше
        }
    }

    attachEventListeners() {
        document.getElementById('groupBtn').addEventListener('click', () => {
            this.studentsManager.showModal();
        });
        document.getElementById('reportBtn').addEventListener('click', () => {
            this.showNotification('Функция отчётов в разработке', 'info');
        });

        const logoutBtn = document.createElement('button');
        logoutBtn.className = 'btn btn-outline';
        logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt"></i> <span class="btn-text">Выход</span>';
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('access_token');
            localStorage.removeItem('selectedGroup');
            window.location.reload();
        });
        document.querySelector('.header-actions').appendChild(logoutBtn);

        if (this.user && this.user.role === 'admin') {
            const adminBtn = document.createElement('button');
            adminBtn.className = 'btn btn-outline';
            adminBtn.innerHTML = '<i class="fas fa-user-shield"></i> <span class="btn-text">Пользователи</span>';
            adminBtn.addEventListener('click', () => this.usersManager.showModal());
            document.querySelector('.header-actions').appendChild(adminBtn);
        }
    }

    openAttendanceModal(lessonId, lesson) {
        this.attendance.showModal(lessonId, lesson);
    }

    showNotification(message, type = 'info') {
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

window.addEventListener('DOMContentLoaded', () => {
    window.app = new AttendanceApp();
});