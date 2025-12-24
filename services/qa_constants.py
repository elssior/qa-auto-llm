"""Stores constants for API endpoint paths."""

# API Endpoint Paths
OPENFLOW_RULES_PATH = "openflowRules"
OPENFLOW_GATEWAYS_PATH = "openflowGateways"
CUSTOM_FEATURE_PATH = "custom-feature"
OPENFLOW_HOPS_PATH = "openflowHops" 
NO_CLEANUP_FEATURE_PATH = "no-cleanup-needed"

# OpenFlow Cookie Prefixes (Example values, adjust as needed)
OPENFLOW_COOKIE_PREFIX = 0xcafe # For Rules
OPENFLOW_GATEWAY_COOKIE_PREFIX = 0xbeef # For Gateways

# Agent configuration
AGENT = {
    "host": "127.0.0.1",
    "port": 8000,
    "base_path": "/api",
    "description": "Агент для генерации трафика и проверки состояния"
}

# Service configurations
SERVICES = {
    "vswitch": [
        {
            "host": "127.0.0.1",
            "port": 7779,
            "base_path": "/api",
            "name": "main",
            "description": "Основной API vswitch"
        },
        {
            "host": "127.0.0.1",
            "port": 7782,
            "base_path": "/",
            "name": "connections",
            "description": "API для connections"
        },
        {
            "host": "127.0.0.1",
            "port": 7785,
            "base_path": "/",
            "name": "filter",
            "description": "API для filter"
        }
    ],
    "services-monitor": {
        "host": "127.0.0.1",
        "port": 7776,
        "base_path": "/"
    },
    "frrouting": {
        "host": "127.0.0.1",
        "port": 7773,
        "base_path": "/api"
    },
    "netmap": {
        "host": "127.0.0.1",
        "port": 1155,
        "base_path": "/api"
    },
    "cluster": {
        "host": "127.0.0.1",
        "port": 9933,
        "base_path": "/api"
    },
    "analytics-server": {
        "host": "127.0.0.1",
        "port": 4014,
        "base_path": "/api"
    },
    "objects": {
        "host": "127.0.0.1",
        "port": 7784,
        "base_path": "/"
    },
    "ids": {
        "host": "127.0.0.1",
        "port": 7777,
        "base_path": "/api"
    },
    "centec": {
        "host": "127.0.0.1",
        "port": 7783,
        "base_path": "/api"
    },
    "core": {
        "host": "127.0.0.1",
        "port": 4006,
        "base_path": "/api"
    },
    "csi-server": {
        "host": "127.0.0.1",
        "port": 2999,
        "base_path": "/api"
    }
}

# Конфигурация SSH туннелей для автоматического проброса портов
# Ключ: имя сервиса, Значение: (локальный_порт, удаленный_порт, удаленный_хост)
TUNNEL_CONFIG = {
    "mirada-agent": (8000, 8000, "127.0.0.1"),
    "cluster": (9933, 9933, "192.0.2.193"),
    "frrouting": (7773, 7773, "127.0.0.1"),
    "netmap": (1155, 1155, "127.0.0.1"),
    "services-monitor": (7776, 7776, "127.0.0.1"),
    "vswitch": (7779, 7779, "127.0.0.1"),
    "vswitch-connections": (7782, 7782, "192.0.2.10"),
    "vswitch-filter": (7785, 7785, "192.0.2.10"),
    "ad": (7778, 7778, "127.0.0.1"),
    "objects": (7784, 7784, "127.0.0.1"),
    "ids": (7777, 7777, "127.0.0.1"),
    "analytics-server": (4014, 4014, "127.0.0.1"),
    "centec": (7783, 7783, "127.0.0.1"),
    "core": (4006, 4006, "127.0.0.1"),
    "csi-server": (2999, 2999, "127.0.0.1")
}