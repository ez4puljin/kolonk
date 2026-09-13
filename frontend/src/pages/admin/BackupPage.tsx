import { useMemo, useRef, useState } from "react";
import {
  Archive,
  Clock,
  Cloud,
  CloudDownload,
  CloudUpload,
  Download,
  FolderCog,
  HardDrive,
  Images,
  RotateCcw,
  Settings2,
  TriangleAlert,
} from "lucide-react";

import { api, errorMessage } from "../../api/client";
import {
  useBackupDirectory,
  useBackups,
  useCreateBackupMutation,
  useGdriveDownloadMutation,
  useGdriveStatus,
  useGdriveUploadMutation,
  useRestoreBackupMutation,
  useRestoreUploadsMutation,
  useSaveGdriveMutation,
  useSetBackupDirectoryMutation,
  useUploadsArchive,
} from "../../api/queries/system";
import type { BackupFile } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { formatBytes, formatDateTime } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { KeyValue, TextAreaField, TextField, ToggleField } from "../catalog/_shared";

/** Сервер `filename` талбараар буцаадаг (DTO-д `name`) — хоёуланг нь дэмжинэ. */
type BackupRow = BackupFile;

function fileNameOf(row: BackupRow): string {
  return row.filename;
}

export function BackupPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [createOpen, setCreateOpen] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<BackupRow | null>(null);
  const [confirmWord, setConfirmWord] = useState("");
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const [dirOpen, setDirOpen] = useState(false);
  const [dirDraft, setDirDraft] = useState("");
  const [dirError, setDirError] = useState<string | null>(null);

  // Google Drive
  const [gdriveOpen, setGdriveOpen] = useState(false);
  const [gdriveEnabled, setGdriveEnabled] = useState(false);
  const [gdriveFolder, setGdriveFolder] = useState("");
  const [gdriveKey, setGdriveKey] = useState("");
  const [gdriveClearKey, setGdriveClearKey] = useState(false);
  const [gdriveError, setGdriveError] = useState<string | null>(null);
  const [gdriveUploadOpen, setGdriveUploadOpen] = useState(false);
  const [gdriveDownloadOpen, setGdriveDownloadOpen] = useState(false);
  const keyFileRef = useRef<HTMLInputElement | null>(null);

  const backupsQuery = useBackups();
  const directoryQuery = useBackupDirectory();
  const gdriveQuery = useGdriveStatus();
  const saveGdriveMutation = useSaveGdriveMutation();
  const gdriveUploadMutation = useGdriveUploadMutation();
  const gdriveDownloadMutation = useGdriveDownloadMutation();
  const gdrive = gdriveQuery.data ?? null;

  // Зургийн архив
  const uploadsQuery = useUploadsArchive();
  const uploadsArchive = uploadsQuery.data ?? null;
  const restoreUploadsMutation = useRestoreUploadsMutation();
  const [uploadsRestoreOpen, setUploadsRestoreOpen] = useState(false);
  const [uploadsConfirmWord, setUploadsConfirmWord] = useState("");
  const [uploadsRestoreError, setUploadsRestoreError] = useState<string | null>(null);

  const submitUploadsRestore = (): void => {
    if (uploadsConfirmWord.trim().toUpperCase() !== t.admin.restoreWord) return;
    setUploadsRestoreError(null);
    restoreUploadsMutation.mutate(t.admin.restoreWord, {
      onSuccess: (result) => {
        toastSuccess(`${t.admin.uploadsRestored}: ${result.files} ${t.admin.uploadsFiles}`);
        setUploadsRestoreOpen(false);
        setUploadsConfirmWord("");
      },
      onError: (error) => setUploadsRestoreError(errorMessage(error)),
    });
  };

  const openGdriveEditor = (): void => {
    setGdriveEnabled(gdrive?.enabled ?? false);
    setGdriveFolder(gdrive?.folder_id ?? "");
    setGdriveKey("");
    setGdriveClearKey(false);
    setGdriveError(null);
    setGdriveOpen(true);
  };

  const readKeyFile = (file: File | null): void => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setGdriveKey(String(reader.result ?? ""));
      setGdriveClearKey(false);
    };
    reader.readAsText(file);
  };

  const saveGdrive = (): void => {
    setGdriveError(null);
    const key = gdriveKey.trim();
    saveGdriveMutation.mutate(
      {
        enabled: gdriveEnabled,
        folder_id: gdriveFolder.trim(),
        // Түлхүүр оруулаагүй бол хадгалсныг хэвээр үлдээнэ (null); устгах бол "".
        service_account_json: gdriveClearKey ? "" : key === "" ? null : key,
      },
      {
        onSuccess: () => {
          toastSuccess(t.admin.gdriveSaved);
          setGdriveOpen(false);
        },
        onError: (error) => setGdriveError(errorMessage(error)),
      },
    );
  };

  const uploadNow = (): void => {
    gdriveUploadMutation.mutate(undefined, {
      onSuccess: () => {
        toastSuccess(t.admin.gdriveUploaded);
        setGdriveUploadOpen(false);
      },
      onError: (error) => {
        toastError(errorMessage(error));
        setGdriveUploadOpen(false);
      },
    });
  };

  const downloadFromDrive = (): void => {
    gdriveDownloadMutation.mutate(undefined, {
      onSuccess: () => {
        toastSuccess(t.admin.gdriveDownloaded);
        setGdriveDownloadOpen(false);
      },
      onError: (error) => {
        toastError(errorMessage(error));
        setGdriveDownloadOpen(false);
      },
    });
  };
  const createMutation = useCreateBackupMutation();
  const restoreMutation = useRestoreBackupMutation();
  const setDirMutation = useSetBackupDirectoryMutation();

  const directory = directoryQuery.data ?? null;

  const openDirEditor = (): void => {
    // Анхдагч хавтас үед хоосон эхэлнэ — хэрэглэгч өөрийн замаа бичнэ.
    setDirDraft(directory && !directory.is_default ? directory.directory : "");
    setDirError(null);
    setDirOpen(true);
  };

  const saveDirectory = (trimmed: string): void => {
    setDirError(null);
    setDirMutation.mutate(trimmed, {
      onSuccess: () => {
        toastSuccess(t.admin.backupDirSaved);
        setDirOpen(false);
      },
      onError: (error) => setDirError(errorMessage(error)),
    });
  };

  const rows = useMemo<BackupRow[]>(() => backupsQuery.data?.items ?? [], [backupsQuery.data]);

  const totals = useMemo(
    () => ({
      count: rows.length,
      bytes: rows.reduce((sum, row) => sum + (row.size_bytes ?? 0), 0),
      latest: rows[0]?.created_at ?? null,
    }),
    [rows],
  );
  const latestRolling = useMemo(() => rows.find((row) => row.filename === "kolonk-latest.dump") ?? null, [rows]);

  const download = async (row: BackupRow): Promise<void> => {
    const name = fileNameOf(row);
    setDownloading(name);
    try {
      await api.download(`/api/backups/${encodeURIComponent(name)}/download`, undefined, name);
    } catch (error) {
      toastError(errorMessage(error));
    } finally {
      setDownloading(null);
    }
  };

  const createBackup = (): void => {
    createMutation.mutate(undefined, {
      onSuccess: () => {
        toastSuccess(t.admin.backupCreated_);
        setCreateOpen(false);
      },
      onError: (error) => {
        toastError(errorMessage(error));
        setCreateOpen(false);
      },
    });
  };

  const submitRestore = (): void => {
    if (!restoreTarget || confirmWord.trim().toUpperCase() !== t.admin.restoreWord) return;
    setRestoreError(null);
    restoreMutation.mutate(
      { name: fileNameOf(restoreTarget), confirm: t.admin.restoreWord },
      {
        onSuccess: () => {
          setRestoreTarget(null);
          setConfirmWord("");
          toastSuccess(t.common.saved);
        },
        onError: (error) => setRestoreError(errorMessage(error)),
      },
    );
  };

  const columns: Column<BackupRow>[] = [
    {
      key: "name",
      header: t.admin.backupFile,
      primary: true,
      render: (row) => <span className="num font-semibold break-all">{fileNameOf(row)}</span>,
    },
    {
      key: "created_at",
      header: t.admin.backupCreated,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "size",
      header: t.admin.backupSize,
      align: "right",
      numeric: true,
      render: (row) => formatBytes(row.size_bytes),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            size="md"
            icon={<Download />}
            loading={downloading === fileNameOf(row)}
            onClick={() => void download(row)}
          >
            {t.admin.download}
          </Button>
          <Button
            variant="danger"
            size="md"
            icon={<RotateCcw />}
            onClick={() => {
              setRestoreTarget(row);
              setConfirmWord("");
              setRestoreError(null);
            }}
          >
            {t.admin.restore}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.admin.backup}
        subtitle={t.admin.backupSubtitle}
        actions={
          <Button
            variant="primary"
            size="lg"
            icon={<Archive />}
            loading={createMutation.isPending}
            onClick={() => setCreateOpen(true)}
          >
            {t.admin.createBackup}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.admin.backupCount} value={totals.count} tone="neutral" />
        <StatBox label={t.admin.backupSize} value={formatBytes(totals.bytes)} tone="action" />
        <StatBox
          label={t.admin.backupCreated}
          value={totals.latest ? formatDateTime(totals.latest) : "—"}
          tone="success"
        />
      </div>

      {/* Хадгалах хавтас — серверийн бүтэн зам */}
      <Card
        title={t.admin.backupDir}
        actions={
          <Button variant="secondary" size="md" icon={<FolderCog />} onClick={openDirEditor}>
            {t.admin.editPath}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <span className="num min-w-0 flex-1 break-all text-[15px] font-semibold text-ink">
            {directory ? directory.directory : "…"}
          </span>
          {directory ? (
            <span className="flex items-center gap-2 text-sm text-ink-soft">
              <HardDrive className="h-4 w-4" />
              {t.admin.backupDirFree}: <b className="num text-ink">{directory.free_mb} МБ</b>
            </span>
          ) : null}
          {directory?.is_default ? (
            <span className="rounded-full bg-surface-sunken px-3 py-1 text-xs font-semibold text-ink-soft">
              {t.admin.backupDirDefault}
            </span>
          ) : null}
        </div>
      </Card>

      {/* Автомат хуваарь */}
      <Card title={t.admin.backupSchedule}>
        <div className="flex flex-col gap-3">
          <p className="flex items-start gap-3 text-[15px] text-ink-soft">
            <Clock className="mt-0.5 h-5 w-5 shrink-0" />
            {t.admin.backupScheduleHint}
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <KeyValue
              label={t.admin.backupLatest}
              value={latestRolling ? `${formatDateTime(latestRolling.created_at)} · ${formatBytes(latestRolling.size_bytes)}` : "—"}
              numeric
            />
            <KeyValue
              label={t.admin.uploadsArchive}
              value={
                uploadsArchive?.exists
                  ? `${formatDateTime(uploadsArchive.created_at)} · ${formatBytes(uploadsArchive.size_bytes)} · ${uploadsArchive.files} ${t.admin.uploadsFiles}`
                  : `— · ${uploadsArchive?.files ?? 0} ${t.admin.uploadsFiles}`
              }
              numeric
            />
          </div>
          <p className="text-sm text-ink-soft">{t.admin.uploadsArchiveHint}</p>
          {uploadsArchive?.exists ? (
            <div>
              <Button
                variant="secondary"
                size="md"
                icon={<Images />}
                onClick={() => {
                  setUploadsConfirmWord("");
                  setUploadsRestoreError(null);
                  setUploadsRestoreOpen(true);
                }}
              >
                {t.admin.uploadsRestore}
              </Button>
            </div>
          ) : null}
        </div>
      </Card>

      {/* Google Drive */}
      <Card
        title={t.admin.gdrive}
        subtitle={t.admin.gdriveSubtitle}
        actions={
          <Button variant="secondary" size="md" icon={<Settings2 />} onClick={openGdriveEditor}>
            {t.admin.gdriveConfigure}
          </Button>
        }
      >
        {gdriveQuery.isLoading ? (
          <p className="text-sm text-ink-soft">…</p>
        ) : !gdrive?.configured ? (
          <div className="flex flex-col gap-4">
            <p className="flex items-start gap-3 text-[15px] text-ink-soft">
              <Cloud className="mt-0.5 h-5 w-5 shrink-0" />
              {t.admin.gdriveNotConfigured}
            </p>
            <div>
              <span className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">{t.admin.gdriveHowTo}</span>
              <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm text-ink-soft">
                {t.admin.gdriveSteps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue label={t.admin.gdriveClientEmail} value={gdrive.client_email ?? "—"} />
              <KeyValue label={t.admin.gdriveFolder} value={gdrive.folder_name ?? gdrive.folder_id} />
              <KeyValue
                label={t.admin.gdriveRemoteFile}
                value={
                  gdrive.remote
                    ? `${formatBytes(gdrive.remote.size_bytes)} · ${formatDateTime(gdrive.remote.modified_at)}`
                    : gdrive.check_error
                      ? "—"
                      : t.admin.gdriveRemoteNone
                }
                numeric
              />
              <KeyValue
                label={t.admin.gdriveLastUpload}
                value={gdrive.last_upload_at ? formatDateTime(gdrive.last_upload_at) : "—"}
                numeric
              />
              <KeyValue
                label={t.admin.gdriveRemoteUploads}
                value={
                  gdrive.remote_uploads
                    ? `${formatBytes(gdrive.remote_uploads.size_bytes)} · ${formatDateTime(gdrive.remote_uploads.modified_at)}`
                    : "—"
                }
                numeric
              />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  gdrive.enabled ? "bg-success-soft text-success-dark" : "bg-surface-sunken text-ink-soft"
                }`}
              >
                {t.admin.gdriveEnabled}: {gdrive.enabled ? t.common.yes : t.common.no}
              </span>
              <Button
                variant="primary"
                size="md"
                icon={<CloudUpload />}
                loading={gdriveUploadMutation.isPending}
                onClick={() => setGdriveUploadOpen(true)}
              >
                {t.admin.gdriveUploadNow}
              </Button>
              <Button
                variant="secondary"
                size="md"
                icon={<CloudDownload />}
                loading={gdriveDownloadMutation.isPending}
                disabled={!gdrive.remote}
                onClick={() => setGdriveDownloadOpen(true)}
              >
                {t.admin.gdriveDownload}
              </Button>
            </div>
            {gdrive.check_error || gdrive.last_error ? (
              <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
                {t.admin.gdriveLastError}: {gdrive.check_error ?? gdrive.last_error}
              </p>
            ) : null}
          </div>
        )}
      </Card>

      <div className="flex items-start gap-4 rounded-xl border border-warning/30 bg-warning-soft px-5 py-4">
        <TriangleAlert className="mt-0.5 h-6 w-6 shrink-0 text-warning-dark" />
        <p className="text-[15px] font-medium text-warning-dark">{t.admin.restoreWarning}</p>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => fileNameOf(row)}
          loading={backupsQuery.isLoading}
          empty={
            <EmptyState
              icon={<Archive className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => setCreateOpen(true)}>
                  {t.admin.createBackup}
                </Button>
              }
            />
          }
        />
      </Card>

      <ConfirmDialog
        open={createOpen}
        title={t.admin.createBackup}
        message={t.admin.createBackupConfirm}
        variant="primary"
        confirmLabel={t.admin.createBackup}
        loading={createMutation.isPending}
        onConfirm={createBackup}
        onCancel={() => setCreateOpen(false)}
      />

      <Modal
        open={dirOpen}
        onClose={() => setDirOpen(false)}
        size="md"
        title={t.admin.backupDir}
        dismissible={!setDirMutation.isPending}
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              disabled={setDirMutation.isPending}
              onClick={() => saveDirectory("")}
            >
              {t.admin.useDefaultPath}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={dirDraft.trim() === ""}
              loading={setDirMutation.isPending}
              onClick={() => saveDirectory(dirDraft.trim())}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label={t.admin.backupDir}
            value={dirDraft}
            onChange={setDirDraft}
            placeholder="D:\Kolonk\backups"
            hint={t.admin.backupDirHint}
          />
          {dirError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {dirError}
            </p>
          ) : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={gdriveUploadOpen}
        title={t.admin.gdriveUploadNow}
        message={t.admin.gdriveUploadNowConfirm}
        variant="primary"
        confirmLabel={t.admin.gdriveUploadNow}
        loading={gdriveUploadMutation.isPending}
        onConfirm={uploadNow}
        onCancel={() => setGdriveUploadOpen(false)}
      />

      <ConfirmDialog
        open={gdriveDownloadOpen}
        title={t.admin.gdriveDownload}
        message={t.admin.gdriveDownloadConfirm}
        variant="warning"
        confirmLabel={t.admin.gdriveDownload}
        loading={gdriveDownloadMutation.isPending}
        onConfirm={downloadFromDrive}
        onCancel={() => setGdriveDownloadOpen(false)}
      />

      <Modal
        open={gdriveOpen}
        onClose={() => setGdriveOpen(false)}
        size="lg"
        title={t.admin.gdrive}
        subtitle={t.admin.gdriveSubtitle}
        dismissible={!saveGdriveMutation.isPending}
        footer={
          <>
            <Button variant="secondary" size="md" disabled={saveGdriveMutation.isPending} onClick={() => setGdriveOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button variant="primary" size="md" loading={saveGdriveMutation.isPending} onClick={saveGdrive}>
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <ToggleField
            label={t.admin.gdriveEnabled}
            hint={t.admin.gdriveEnabledHint}
            value={gdriveEnabled}
            onChange={setGdriveEnabled}
          />
          <TextField
            label={t.admin.gdriveFolderId}
            value={gdriveFolder}
            onChange={setGdriveFolder}
            placeholder="1AbCdEfGhIjKlMnOpQrStUvWxYz"
            hint={t.admin.gdriveFolderIdHint}
          />
          <div className="flex flex-col gap-2">
            <TextAreaField
              label={t.admin.gdriveKey}
              value={gdriveKey}
              onChange={(value) => {
                setGdriveKey(value);
                setGdriveClearKey(false);
              }}
              rows={5}
              placeholder={gdrive?.client_email && !gdriveClearKey ? `${t.admin.gdriveKeySaved}: ${gdrive.client_email}` : "{ \"type\": \"service_account\", … }"}
            />
            <span className="text-xs text-ink-soft">{t.admin.gdriveKeyHint}</span>
            <div className="flex flex-wrap gap-2">
              <input
                ref={keyFileRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => readKeyFile(event.target.files?.[0] ?? null)}
              />
              <Button variant="secondary" size="md" onClick={() => keyFileRef.current?.click()}>
                {t.admin.gdriveKeyFile}
              </Button>
              {gdrive?.client_email ? (
                <Button
                  variant={gdriveClearKey ? "danger" : "ghost"}
                  size="md"
                  onClick={() => {
                    setGdriveClearKey((v) => !v);
                    setGdriveKey("");
                  }}
                >
                  {t.admin.gdriveKeyClear}
                </Button>
              ) : null}
            </div>
          </div>
          <div>
            <span className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">{t.admin.gdriveHowTo}</span>
            <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm text-ink-soft">
              {t.admin.gdriveSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
          {gdriveError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{gdriveError}</p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={uploadsRestoreOpen}
        onClose={() => setUploadsRestoreOpen(false)}
        size="md"
        title={t.admin.uploadsRestore}
        subtitle={t.admin.uploadsRestoreHint}
        dismissible={!restoreUploadsMutation.isPending}
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              disabled={restoreUploadsMutation.isPending}
              onClick={() => setUploadsRestoreOpen(false)}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="warning"
              size="md"
              disabled={uploadsConfirmWord.trim().toUpperCase() !== t.admin.restoreWord}
              loading={restoreUploadsMutation.isPending}
              onClick={submitUploadsRestore}
            >
              {t.admin.uploadsRestore}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label={t.admin.restoreConfirm}
            value={uploadsConfirmWord}
            onChange={setUploadsConfirmWord}
            placeholder={t.admin.restoreWord}
            hint={`${t.common.confirm}: ${t.admin.restoreWord}`}
          />
          {uploadsRestoreError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {uploadsRestoreError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={restoreTarget !== null}
        onClose={() => setRestoreTarget(null)}
        size="md"
        title={t.admin.restore}
        subtitle={restoreTarget ? fileNameOf(restoreTarget) : ""}
        dismissible={!restoreMutation.isPending}
        footer={
          <>
            <Button
              variant="secondary"
              size="md"
              disabled={restoreMutation.isPending}
              onClick={() => setRestoreTarget(null)}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="danger"
              size="md"
              disabled={confirmWord.trim().toUpperCase() !== t.admin.restoreWord}
              loading={restoreMutation.isPending}
              onClick={submitRestore}
            >
              {t.admin.restore}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-start gap-4 rounded-xl border border-danger/30 bg-danger-soft px-4 py-3">
            <TriangleAlert className="mt-0.5 h-6 w-6 shrink-0 text-danger-dark" />
            <p className="text-[15px] font-semibold text-danger-dark">{t.admin.restoreWarning}</p>
          </div>
          <TextField
            label={t.admin.restoreConfirm}
            value={confirmWord}
            onChange={setConfirmWord}
            placeholder={t.admin.restoreWord}
            hint={`${t.common.confirm}: ${t.admin.restoreWord}`}
          />
          {restoreError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {restoreError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default BackupPage;
