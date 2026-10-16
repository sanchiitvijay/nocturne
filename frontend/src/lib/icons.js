// Icon keys used by the API (navigation) and by domain values (device roles, event categories) → react-icons.
import {
  LuActivity, LuBatteryCharging, LuBell, LuBrickWall, LuCable, LuCircleHelp, LuCpu, LuDatabase, LuGauge, LuHardDrive,
  LuMapPin, LuMonitor, LuNetwork, LuPackage, LuPlug, LuPrinter, LuRadioTower, LuRoute, LuRouter, LuServer, LuShield,
  LuTicket, LuWifi, LuZap,
} from "react-icons/lu";

export const NAV_ICONS = {
  pulse: LuActivity, bell: LuBell, chip: LuCpu, pin: LuMapPin, ticket: LuTicket, bolt: LuZap, database: LuDatabase, shield: LuShield,
};

const ROLE_ICONS = {
  switch: LuNetwork, "access point": LuWifi, ups: LuBatteryCharging, firewall: LuBrickWall, router: LuRouter,
  controller: LuRadioTower, printer: LuPrinter,
};

const CATEGORY_ICONS = {
  connectivity: LuActivity, interface: LuCable, routing: LuRoute, wireless: LuWifi, power: LuPlug, hardware: LuHardDrive,
  performance: LuGauge, monitoring: LuMonitor, inventory: LuPackage,
};

export const navIcon = (key) => NAV_ICONS[key] || LuCircleHelp;
export const roleIcon = (role) => ROLE_ICONS[role] || LuServer;
export const categoryIcon = (category) => CATEGORY_ICONS[category] || LuCircleHelp;
