import { Utils } from './utils.js';

export class CalendarManager {
    constructor(app) {
        this.app = app;
        this.selectedDate = new Date();
        this.flatpickr = null;
    }

    init() {
        const input = document.getElementById('datePicker');
        if (!input) return;

        this.flatpickr = flatpickr(input, {
            locale: 'ru',
            dateFormat: 'd.m.Y',
            defaultDate: this.selectedDate,
            onChange: async (dates) => {
                if (dates.length) {
                    this.selectedDate = dates[0];
                    this.updateDateText();
                    try {
                        await this.app.refreshSchedule();
                    } catch (err) {
                        console.error('Error refreshing schedule on date change:', err);
                    }
                }
            }
        });

        this.updateDateText();
    }

    updateDateText() {
        const dateText = document.getElementById('selectedDateText');
        if (!dateText) return;

        const today = new Date();
        if (this.selectedDate.toDateString() === today.toDateString()) {
            dateText.textContent = 'Сегодня';
        } else {
            dateText.textContent = Utils.formatDate(this.selectedDate);
        }
    }

    getSelectedDate() {
        return new Date(this.selectedDate);
    }

    setSelectedDate(date) {
        this.selectedDate = new Date(date);
        if (this.flatpickr) {
            this.flatpickr.setDate(this.selectedDate);
        }
        this.updateDateText();
    }
}