import { useState } from 'react';
import { EnvironmentDetail, EnvironmentSaveBody } from '../services/environments';
import { useEnvironments } from '../hooks/useEnvironments';

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function envDotColor(name: string): string {
  const n = name.toLowerCase();
  if (n.includes('prod')) return 'bg-success';
  if (n.includes('beta') || n.includes('staging') || n.includes('stage') || n.includes('dev')) return 'bg-warning';
  return 'bg-primary';
}

// ── Inline page-local components ─────────────────────────────────────────────

interface ModalProps {
  initial?: EnvironmentDetail;
  onClose: () => void;
  onSave: (data: EnvironmentSaveBody) => void;
  isPending: boolean;
  serverError: string;
}

function EnvironmentModal({ initial, onClose, onSave, isPending, serverError }: ModalProps) {
  const isEdit = !!initial;

  const [name,          setName]          = useState(initial?.name ?? '');
  const [baseUrl,       setBaseUrl]       = useState(initial?.baseUrl ?? '');
  const [description,   setDescription]   = useState(initial?.description ?? '');
  const [isActive,      setIsActive]      = useState(initial?.isActive ?? true);
  const [loginEmail,    setLoginEmail]    = useState(initial?.loginEmail ?? '');
  const [loginPassword, setLoginPassword] = useState('');
  const [showPassword,  setShowPassword]  = useState(false);

  const [nameError,     setNameError]     = useState('');
  const [urlError,      setUrlError]      = useState('');
  const [emailError,    setEmailError]    = useState('');
  const [passwordError, setPasswordError] = useState('');

  function validate(): boolean {
    let ok = true;
    if (!name.trim()) { setNameError('Name is required.'); ok = false; } else setNameError('');
    if (!baseUrl.startsWith('https://')) { setUrlError('Enter a valid URL starting with https://'); ok = false; } else setUrlError('');
    if (!loginEmail.trim()) { setEmailError('Login email is required.'); ok = false; } else setEmailError('');
    if (!isEdit && !loginPassword.trim()) { setPasswordError('Password is required.'); ok = false; } else setPasswordError('');
    return ok;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    const body: EnvironmentSaveBody = {
      name: name.trim(),
      baseUrl: baseUrl.trim(),
      description: description.trim(),
      isActive,
      loginEmail: loginEmail.trim(),
    };
    if (loginPassword.trim()) body.loginPassword = loginPassword.trim();
    onSave(body);
  }

  const isFormValid =
    name.trim().length > 0 &&
    baseUrl.startsWith('https://') &&
    loginEmail.trim().length > 0 &&
    (isEdit || loginPassword.trim().length > 0);

  return (
    <div
      className="fixed inset-0 bg-surface-sidebar/40 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[92vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>
                {isEdit ? 'edit' : 'add_circle'}
              </span>
            </div>
            <h2 className="font-semibold text-text-primary">
              {isEdit ? 'Edit environment' : 'Add environment'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary hover:bg-surface-muted transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto">
          <div className="px-6 py-5 space-y-5">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Name <span className="text-error">*</span>
              </label>
              <input
                autoFocus type="text" value={name}
                onChange={(e) => { setName(e.target.value); if (nameError) setNameError(''); }}
                placeholder="Production"
                className={`w-full border rounded-xl px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                  nameError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                }`}
              />
              {nameError && (
                <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                  <span className="material-symbols-outlined" style={{ fontSize: 12 }}>error</span>{nameError}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Base URL <span className="text-error">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>link</span>
                </span>
                <input
                  type="text" value={baseUrl}
                  onChange={(e) => { setBaseUrl(e.target.value); if (urlError) setUrlError(''); }}
                  placeholder="https://app.example.com"
                  className={`w-full border rounded-xl pl-9 pr-3.5 py-2.5 text-sm font-mono-code text-text-primary placeholder:text-text-secondary placeholder:font-sans bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                    urlError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                  }`}
                />
              </div>
              {urlError && (
                <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                  <span className="material-symbols-outlined" style={{ fontSize: 12 }}>error</span>{urlError}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Description
                <span className="ml-1.5 text-xs font-normal text-text-secondary">(optional)</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this environment…"
                rows={2}
                className="w-full border border-border-subtle rounded-xl px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 resize-none transition-colors"
              />
            </div>

            <div className="border-t border-border-subtle pt-1">
              <div className="flex items-center gap-2 mb-4">
                <span className="material-symbols-outlined text-text-secondary" style={{ fontSize: 16 }}>lock</span>
                <p className="text-sm font-medium text-text-primary">Dashboard credentials</p>
              </div>
              <p className="text-xs text-text-secondary mb-4 -mt-2 leading-relaxed">
                Used to log in to the dashboard when running tests. Stored in the database.
              </p>

              <div className="mb-4">
                <label className="block text-sm font-medium text-text-primary mb-1.5">
                  Login email <span className="text-error">*</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary">
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>mail</span>
                  </span>
                  <input
                    type="email" value={loginEmail}
                    onChange={(e) => { setLoginEmail(e.target.value); if (emailError) setEmailError(''); }}
                    placeholder="you@example.com"
                    className={`w-full border rounded-xl pl-9 pr-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                      emailError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                    }`}
                  />
                </div>
                {emailError && (
                  <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                    <span className="material-symbols-outlined" style={{ fontSize: 12 }}>error</span>{emailError}
                  </p>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-medium text-text-primary">
                    Password {!isEdit && <span className="text-error">*</span>}
                  </label>
                  {isEdit && initial?.hasPassword && !loginPassword && (
                    <span className="inline-flex items-center gap-1 text-xs text-success font-medium">
                      <span className="material-symbols-outlined" style={{ fontSize: 13 }}>check_circle</span>
                      Password saved — leave blank to keep
                    </span>
                  )}
                </div>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-secondary">
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>key</span>
                  </span>
                  <input
                    type={showPassword ? 'text' : 'password'} value={loginPassword}
                    onChange={(e) => { setLoginPassword(e.target.value); if (passwordError) setPasswordError(''); }}
                    placeholder={isEdit ? '••••••••' : 'Enter password'}
                    className={`w-full border rounded-xl pl-9 pr-10 py-2.5 text-sm text-text-primary placeholder:text-text-secondary bg-surface-main focus:outline-none focus:ring-2 transition-colors ${
                      passwordError ? 'border-error focus:ring-error/20 focus:border-error' : 'border-border-subtle focus:ring-primary/20 focus:border-primary/40'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition-colors"
                    tabIndex={-1}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                      {showPassword ? 'visibility_off' : 'visibility'}
                    </span>
                  </button>
                </div>
                {passwordError && (
                  <p className="mt-1.5 text-xs text-error flex items-center gap-1">
                    <span className="material-symbols-outlined" style={{ fontSize: 12 }}>error</span>{passwordError}
                  </p>
                )}
              </div>

              {isEdit && (
                <div className="mt-4">
                  <label className="block text-sm font-medium text-text-primary mb-1.5">Publisher</label>
                  <div className="flex items-center gap-2 bg-surface-muted border border-border-subtle rounded-xl px-3.5 py-2.5">
                    <span className="material-symbols-outlined text-primary flex-shrink-0" style={{ fontSize: 15 }}>apartment</span>
                    <span className="text-xs text-text-primary">
                      {initial?.publisher || <span className="text-text-secondary italic">Not yet detected — will be set on first run</span>}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-border-subtle" />

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">Active</p>
                <p className="text-xs text-text-secondary mt-0.5">Only active environments appear in run dialogs</p>
              </div>
              <button
                type="button" role="switch" aria-checked={isActive}
                onClick={() => setIsActive((v) => !v)}
                className={`relative w-11 h-6 rounded-full transition-colors duration-200 flex-shrink-0 focus:outline-none focus:ring-2 focus:ring-primary/30 ${
                  isActive ? 'bg-primary' : 'bg-border-subtle'
                }`}
              >
                <span className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${isActive ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>

            {serverError && (
              <div className="flex items-start gap-2 bg-error/5 border border-error/20 rounded-xl px-3.5 py-3">
                <span className="material-symbols-outlined text-error flex-shrink-0 mt-0.5" style={{ fontSize: 16 }}>error</span>
                <p className="text-sm text-error">{serverError}</p>
              </div>
            )}
          </div>

          <div className="flex gap-3 px-6 py-4 border-t border-border-subtle flex-shrink-0 bg-surface-muted/30">
            <button type="button" onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !isFormValid}
              className={`flex-1 bg-primary text-white rounded-xl py-2.5 text-sm font-semibold transition-all flex items-center justify-center gap-2 ${
                !isFormValid || isPending
                  ? 'opacity-60 cursor-not-allowed'
                  : 'hover:bg-primary/90 hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/25 active:translate-y-0'
              }`}
            >
              {isPending && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
              {isEdit ? 'Save Changes' : 'Create environment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DeleteConfirmModal({
  env, onClose, onConfirm, isPending,
}: {
  env: EnvironmentDetail;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-surface-sidebar/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-surface-main rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 pt-6 pb-4">
          <div className="w-12 h-12 rounded-2xl bg-error/10 flex items-center justify-center mb-4">
            <span className="material-symbols-outlined text-error" style={{ fontSize: 24, fontVariationSettings: '"FILL" 1' }}>delete</span>
          </div>
          <h2 className="font-semibold text-text-primary mb-1.5">Delete environment?</h2>
          <p className="text-sm text-text-secondary leading-relaxed">
            <span className="font-medium text-text-primary">"{env.name}"</span> will be permanently
            deleted. Any test runs using this environment will also be removed.
          </p>
        </div>
        <div className="flex gap-3 px-6 pb-6">
          <button onClick={onClose} className="flex-1 border border-border-subtle rounded-xl py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className="flex-1 bg-error text-white rounded-xl py-2.5 text-sm font-semibold hover:bg-error/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {isPending && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

function EnvironmentCard({
  env, onEdit, onDelete,
}: {
  env: EnvironmentDetail;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [copied, setCopied] = useState(false);

  function copyUrl() {
    navigator.clipboard.writeText(env.baseUrl).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const credentialsOk = env.loginEmail && env.hasPassword;

  return (
    <div className="bg-surface-main border border-border-subtle rounded-xl p-5 flex flex-col gap-4 hover:border-primary/30 hover:shadow-sm transition-all group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5 ${envDotColor(env.name)}`} />
          <h3 className="font-semibold text-text-primary text-sm truncate">{env.name}</h3>
        </div>
        {env.isActive ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-success/10 border border-success/20 text-success text-xs font-semibold flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-muted border border-border-subtle text-text-secondary text-xs font-medium flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-border-subtle" />Inactive
          </span>
        )}
      </div>

      {env.description && (
        <p className="text-xs text-text-secondary leading-relaxed line-clamp-2 -mt-1">{env.description}</p>
      )}

      <div className="bg-surface-muted rounded-lg px-3 py-2 border border-border-subtle/50">
        <p className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider mb-1">BASE URL</p>
        <button type="button" onClick={copyUrl} title={copied ? 'Copied!' : 'Click to copy'} className="group/url flex items-center justify-between gap-2 w-full">
          <code className="font-mono-code text-xs text-primary truncate text-left select-all">{env.baseUrl}</code>
          <span
            className={`material-symbols-outlined flex-shrink-0 transition-colors ${copied ? 'text-success' : 'text-text-secondary group-hover/url:text-primary'}`}
            style={{ fontSize: 14, fontVariationSettings: copied ? '"FILL" 1' : '"FILL" 0' }}
          >
            {copied ? 'check_circle' : 'content_copy'}
          </span>
        </button>
      </div>

      <div className={`rounded-lg px-3 py-2 border ${credentialsOk ? 'bg-surface-muted border-border-subtle/50' : 'bg-warning/5 border-warning/30'}`}>
        <p className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider mb-1">CREDENTIALS</p>
        {credentialsOk ? (
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-success" style={{ fontSize: 14, fontVariationSettings: '"FILL" 1' }}>lock</span>
            <span className="text-xs text-text-primary truncate">{env.loginEmail}</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-warning" style={{ fontSize: 14 }}>warning</span>
            <span className="text-xs text-warning font-medium">Not configured — click Edit</span>
          </div>
        )}
      </div>

      <div className={`rounded-lg px-3 py-2 border ${env.publisher ? 'bg-surface-muted border-border-subtle/50' : 'bg-warning/5 border-warning/30'}`}>
        <p className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider mb-1">PUBLISHER</p>
        {env.publisher ? (
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 14 }}>apartment</span>
            <span className="text-xs text-text-primary truncate">{env.publisher}</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-warning" style={{ fontSize: 14 }}>warning</span>
            <span className="text-xs text-warning font-medium">Not set — click Edit</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1.5 text-xs text-text-secondary">
        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>schedule</span>
        Created: {timeAgo(env.createdAt)}
      </div>

      <div className="mt-auto pt-3 border-t border-border-subtle flex justify-end gap-2">
        <button onClick={onEdit} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-text-secondary hover:text-primary hover:bg-primary/10 transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>edit</span>Edit
        </button>
        <button onClick={onDelete} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-error hover:bg-error/10 transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>delete</span>Delete
        </button>
      </div>
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-8 text-center">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
        <span className="material-symbols-outlined text-primary" style={{ fontSize: 30, fontVariationSettings: '"FILL" 1' }}>network_node</span>
      </div>
      <h2 className="text-base font-semibold text-text-primary mb-2">No environments yet</h2>
      <p className="text-sm text-text-secondary max-w-xs mb-6 leading-relaxed">
        Each environment holds a base URL and login credentials for the dashboard under test.
      </p>
      <button
        onClick={onCreate}
        className="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-primary/90 transition-colors"
      >
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
        Add Environment
      </button>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function Environments() {
  const {
    environments, isLoading,
    modal, serverError,
    createMutation, updateMutation, deleteMutation,
    openCreate, openEdit, openDelete, closeModal,
  } = useEnvironments();

  return (
    <div className="px-8 py-8 max-w-4xl">

      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Environments</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            Each environment has its own base URL and login credentials. Tests run under the environment you select.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-sm hover:bg-primary/90 transition-all hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/20 active:translate-y-0"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          Add Environment
        </button>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-52 bg-surface-muted rounded-xl animate-pulse" />
          ))}
        </div>
      ) : environments.length === 0 ? (
        <EmptyState onCreate={openCreate} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {environments.map((env) => (
            <EnvironmentCard
              key={env.id}
              env={env}
              onEdit={() => openEdit(env)}
              onDelete={() => openDelete(env)}
            />
          ))}

          {/* Ghost add card */}
          <button
            onClick={openCreate}
            className="rounded-xl border-2 border-dashed border-border-subtle p-5 flex flex-col items-center justify-center gap-2 min-h-[180px] hover:border-primary/40 hover:bg-primary/5 transition-all group"
          >
            <div className="w-10 h-10 rounded-xl bg-surface-muted group-hover:bg-primary/10 flex items-center justify-center transition-colors">
              <span className="material-symbols-outlined text-text-secondary group-hover:text-primary transition-colors" style={{ fontSize: 20 }}>add</span>
            </div>
            <span className="text-sm font-medium text-text-secondary group-hover:text-primary transition-colors">
              Add environment
            </span>
          </button>
        </div>
      )}

      {/* Modals */}
      {modal?.type === 'create' && (
        <EnvironmentModal
          onClose={closeModal}
          onSave={(body) => createMutation.mutate(body)}
          isPending={createMutation.isPending}
          serverError={serverError}
        />
      )}

      {modal?.type === 'edit' && (
        <EnvironmentModal
          initial={modal.env}
          onClose={closeModal}
          onSave={(body) => updateMutation.mutate({ id: modal.env.id, body })}
          isPending={updateMutation.isPending}
          serverError={serverError}
        />
      )}

      {modal?.type === 'delete' && (
        <DeleteConfirmModal
          env={modal.env}
          onClose={closeModal}
          onConfirm={() => deleteMutation.mutate(modal.env.id)}
          isPending={deleteMutation.isPending}
        />
      )}
    </div>
  );
}
