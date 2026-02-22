# Frontend Specifications

## Overview

A modern, responsive web interface for DBManager, built with React, Vite, and shadcn/ui.

## Navigation Structure

- **Dashboard**: Overview of system status.
- **Databases**: Manage database connections and backups.
- **Storage**: Manage S3/SMB storage targets.
- **Schedules**: Manage automated backup tasks.
- **Settings**: System configuration and sync.

## Pages & Features

### 1. Layout (Shell)

- **Sidebar**: Collapsible navigation menu.
- **Top Bar**: Breadcrumbs, Theme Toggle (Dark/Light), User Profile/Logout?
- **Global**: Toaster for notifications (Success/Error).

### 2. Dashboard (`/`)

- **Key Metrics**:
  - Total Databases
  - Total Backups stored
  - Storage Usage (if available)
  - Last Backup Status
- **Recent Activity**: Log of recent operations (backups, restores).

### 3. Databases (`/databases`)

- **List View**: Table showing configured databases (Name, Type, Host, ID).
- **Actions**: Add Database (Button).
- **Row Actions**: Backup Now, Restore, Edit, Delete.
- **Add/Edit Modal**: Form with connection details (Provider, Host, Port, User, Password, DB Name).

### 4. Storage Targets (`/storage`)

- **List View**: Table of storage targets (Name, Type, Path/Bucket).
- **Actions**: Add Target.
- **Add Target Wizard**:
  - Step 1: Select Type (S3 / SMB).
  - Step 2: Configure Details (Host/Endpoint, Credentials, Path/Bucket).

### 5. Schedules (`/schedules`)

- **List View**: Cron jobs configured.
- **Create Schedule**: Form to link a Database to a Cron Expression.

### 6. Settings (`/settings`)

- **General**: API URL, Defaults.
- **Config Sync**:
  - Status display.
  - "Sync Now" button.
  - Toggle "Auto Sync".

## Theme & UI

- **Library**: `shadcn/ui` (Radix UI + Tailwind CSS).
- **Style**: "New York" style, Zinc color palette.
- **Dark Mode**: Fully supported.

## State Management

- **React Query**: For server state (fetching/caching API data).
- **Zustand** (optional): For global client state (sidebar open/close, theme).

## API Integration

- Use `axios` or `fetch` with the configured Proxy.
- Standardize error handling to show Toasts.
