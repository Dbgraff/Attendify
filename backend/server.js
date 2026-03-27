const express = require('express');
const path = require('path');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = 3000;

app.use(cors());

// Прокси для API: все запросы, начинающиеся с /api, перенаправляем на бэкенд
app.use('/api', createProxyMiddleware({
    target: 'http://localhost:5000',
    changeOrigin: true,
    pathRewrite: { '^/api': '' }, // убираем /api из пути
}));

// Статические файлы (frontend находится на одном уровне с backend)
app.use(express.static(path.join(__dirname, '..', 'frontend')));

// SPA fallback
app.get(/.*/, (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Frontend server running at http://localhost:${PORT}`);
});