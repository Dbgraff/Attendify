// users.js
import { Utils } from './utils.js';

export class UsersManager {
    constructor(app) {
        this.app = app;
        this.editingUserId = null;
    }

    async showModal() {
        const users = await this.app.api.getUsers();
        const groups = await this.app.api.getGroups();

        const modalHtml = `
            <div class="modal-overlay" id="usersModal">
                <div class="modal modal-lg">
                    <div class="modal-header">
                        <h2 class="modal-title">Управление пользователями</h2>
                        <button class="modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div id="userForm" style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                            <h3 id="formTitle">Добавить пользователя</h3>
                            <div style="display: grid; gap: 8px;">
                                <input type="text" id="editUsername" placeholder="Логин *" class="form-control">
                                <input type="password" id="editPassword" placeholder="Пароль * (оставьте пустым, если не менять)" class="form-control">
                                <input type="text" id="editFullName" placeholder="Полное имя (ФИО)" class="form-control">
                                <select id="editRole" class="form-control">
                                    <option value="teacher">Преподаватель</option>
                                    <option value="headman">Староста</option>
                                    <option value="curator">Куратор</option>
                                </select>
                                <div id="groupField" style="display: none;">
                                    <label>Группа (для старосты):</label>
                                    <select id="editGroupId" class="form-control">
                                        <option value="">Не выбрано</option>
                                        ${groups.map(g => `<option value="${g.code}">${g.code}</option>`).join('')}
                                    </select>
                                </div>
                                <div id="curatorGroupsField" style="display: none;">
                                    <label>Кураторские группы (для куратора):</label>
                                    <select id="editCuratorGroupIds" class="form-control" multiple size="4">
                                        ${groups.map(g => `<option value="${g.code}">${g.code}</option>`).join('')}
                                    </select>
                                    <small>Удерживайте Ctrl для выбора нескольких</small>
                                </div>
                                <button id="saveUserBtn" class="btn btn-primary">Сохранить</button>
                                <button id="cancelEditBtn" class="btn btn-secondary" style="display: none;">Отмена</button>
                            </div>
                        </div>
                        <hr>
                        <div class="users-list" id="usersList"></div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="closeUsersBtn">Закрыть</button>
                    </div>
                </div>
            </div>
        `;

        const container = document.getElementById('modalsContainer');
        container.innerHTML = modalHtml;

        const modal = document.getElementById('usersModal');
        const closeModal = () => modal.remove();

        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        document.getElementById('closeUsersBtn').addEventListener('click', closeModal);

        // Управление видимостью полей в зависимости от роли
        const roleSelect = document.getElementById('editRole');
        const groupField = document.getElementById('groupField');
        const curatorField = document.getElementById('curatorGroupsField');

        const toggleFields = () => {
            const role = roleSelect.value;
            if (role === 'headman') {
                groupField.style.display = 'block';
                curatorField.style.display = 'none';
            } else if (role === 'curator') {
                groupField.style.display = 'none';
                curatorField.style.display = 'block';
            } else {
                groupField.style.display = 'none';
                curatorField.style.display = 'none';
            }
        };
        roleSelect.addEventListener('change', toggleFields);
        toggleFields();

        const saveUserBtn = document.getElementById('saveUserBtn');
        const cancelBtn = document.getElementById('cancelEditBtn');

        const clearForm = () => {
            document.getElementById('editUsername').value = '';
            document.getElementById('editPassword').value = '';
            document.getElementById('editFullName').value = '';
            roleSelect.value = 'teacher';
            document.getElementById('editGroupId').value = '';
            document.getElementById('editCuratorGroupIds').selectedIndex = -1;
            this.editingUserId = null;
            document.getElementById('formTitle').innerText = 'Добавить пользователя';
            cancelBtn.style.display = 'none';
            toggleFields();
        };

        cancelBtn.addEventListener('click', clearForm);

        const renderUsers = async () => {
            const updatedUsers = await this.app.api.getUsers();
            const listDiv = document.getElementById('usersList');
            if (!updatedUsers.length) {
                listDiv.innerHTML = '<p class="empty-state">Пользователей пока нет</p>';
                return;
            }
            listDiv.innerHTML = '';
            for (const user of updatedUsers) {
                const row = document.createElement('div');
                row.className = 'user-row';
                row.innerHTML = `
                    <div class="user-info">
                        <strong>${Utils.escapeHtml(user.username)}</strong> (${Utils.escapeHtml(user.full_name || '')})
                        <div>Роль: ${user.role}</div>
                        <div>Группа: ${user.group_id || '—'}</div>
                        <div>Курируемые группы: ${Array.isArray(user.curator_group_ids) ? user.curator_group_ids.join(', ') : '—'}</div>
                    </div>
                    <div class="user-actions">
                        <button class="btn btn-sm btn-outline edit-user" data-id="${user.id}">✏️</button>
                        <button class="btn btn-sm btn-danger delete-user" data-id="${user.id}">🗑️</button>
                    </div>
                `;
                listDiv.appendChild(row);
            }

            // Обработчики редактирования
            listDiv.querySelectorAll('.edit-user').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const userId = parseInt(btn.dataset.id);
                    const user = updatedUsers.find(u => u.id === userId);
                    if (!user) return;

                    this.editingUserId = userId;
                    document.getElementById('editUsername').value = user.username;
                    document.getElementById('editPassword').value = ''; // не показываем пароль
                    document.getElementById('editFullName').value = user.full_name || '';
                    roleSelect.value = user.role;
                    document.getElementById('editGroupId').value = user.group_id || '';
                    // Для куратора – выбираем группы
                    const curatorSelect = document.getElementById('editCuratorGroupIds');
                    if (user.role === 'curator' && Array.isArray(user.curator_group_ids)) {
                        Array.from(curatorSelect.options).forEach(opt => {
                            opt.selected = user.curator_group_ids.includes(opt.value);
                        });
                    } else {
                        curatorSelect.selectedIndex = -1;
                    }
                    toggleFields();
                    document.getElementById('formTitle').innerText = 'Редактировать пользователя';
                    cancelBtn.style.display = 'inline-block';
                });
            });

            // Обработчики удаления
            listDiv.querySelectorAll('.delete-user').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const userId = parseInt(btn.dataset.id);
                    if (confirm('Удалить пользователя?')) {
                        try {
                            await this.app.api.deleteUser(userId);
                            this.app.showNotification('Пользователь удалён', 'success');
                            this.showModal(); // перезагружаем
                        } catch (err) {
                            this.app.showNotification('Ошибка: ' + err.message, 'error');
                        }
                    }
                });
            });
        };

        await renderUsers();

        // Сохранение (добавление или редактирование)
        saveUserBtn.addEventListener('click', async () => {
            const username = document.getElementById('editUsername').value.trim();
            const password = document.getElementById('editPassword').value.trim();
            const fullName = document.getElementById('editFullName').value.trim();
            const role = roleSelect.value;
            const groupId = document.getElementById('editGroupId').value || null;
            const curatorGroupIds = Array.from(document.getElementById('editCuratorGroupIds').selectedOptions).map(opt => opt.value);

            if (!username) {
                this.app.showNotification('Логин обязателен', 'warning');
                return;
            }
            if (!this.editingUserId && !password) {
                this.app.showNotification('Пароль обязателен при создании', 'warning');
                return;
            }

            const userData = {
                username,
                full_name: fullName,
                role,
                group_id: groupId,
                curator_group_ids: curatorGroupIds
            };
            if (password) userData.password = password;

            try {
                if (this.editingUserId) {
                    await this.app.api.updateUser(this.editingUserId, userData);
                    this.app.showNotification('Пользователь обновлён', 'success');
                } else {
                    await this.app.api.createUser(userData);
                    this.app.showNotification('Пользователь добавлен', 'success');
                }
                clearForm();
                this.showModal(); // перезагружаем
            } catch (err) {
                this.app.showNotification('Ошибка: ' + err.message, 'error');
            }
        });
    }
}