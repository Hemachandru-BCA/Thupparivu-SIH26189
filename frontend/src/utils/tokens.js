// src/utils/tokens.js
// Single source of truth for entity-type CSS token accessors.
// The canonical colors live in index.css as --entity-* vars.

import {
    Users, Database, MapPin, Shield, BarChart3, Clock,
} from 'lucide-react';

export function getEntityColor(type) {
    return `hsl(var(--entity-${type?.toLowerCase() ?? 'device'}))`;
}

export const ENTITY_ICONS = {
    PERSON: Users,
    PHONE: Database,
    VEHICLE: MapPin,
    LOCATION: MapPin,
    ORGANIZATION: Shield,
    ORG: Shield,
    ACCOUNT: BarChart3,
    DEVICE: Database,
    EVENT: Clock,
};

export function getEntityIcon(type) {
    return ENTITY_ICONS[type?.toUpperCase()] ?? Database;
}
