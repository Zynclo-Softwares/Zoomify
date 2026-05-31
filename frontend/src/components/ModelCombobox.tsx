import {
	type KeyboardEvent,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";

const MAX_RESULTS = 80;

type Props = {
	models: string[];
	value: string;
	onChange: (value: string) => void;
	onReplaceKey?: () => void;
	disabled?: boolean;
};

function formatModelLabel(id: string): string {
	const slug = id.includes("/") ? (id.split("/").pop() ?? id) : id;
	return slug
		.split("-")
		.map((word) =>
			word.length <= 4 && /\d/.test(word)
				? word
				: word.charAt(0).toUpperCase() + word.slice(1),
		)
		.join(" ");
}

export default function ModelCombobox({
	models,
	value,
	onChange,
	onReplaceKey,
	disabled,
}: Props) {
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState("");
	const [activeIndex, setActiveIndex] = useState(0);
	const rootRef = useRef<HTMLDivElement>(null);
	const searchRef = useRef<HTMLInputElement>(null);

	useEffect(() => {
		if (!open) return;
		setSearch("");
		setActiveIndex(0);
		window.requestAnimationFrame(() => searchRef.current?.focus());
	}, [open]);

	useEffect(() => {
		const onPointerDown = (e: MouseEvent) => {
			if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
		};
		document.addEventListener("mousedown", onPointerDown);
		return () => document.removeEventListener("mousedown", onPointerDown);
	}, []);

	const filtered = useMemo(() => {
		const q = search.trim().toLowerCase();
		const list = q
			? models.filter(
					(m) =>
						m.toLowerCase().includes(q) ||
						formatModelLabel(m).toLowerCase().includes(q),
				)
			: models;
		const sliced = list.slice(0, MAX_RESULTS);
		if (value && !sliced.includes(value) && models.includes(value)) {
			return [value, ...sliced.filter((m) => m !== value)];
		}
		return sliced;
	}, [models, search, value]);

	const pick = (id: string) => {
		onChange(id);
		setOpen(false);
	};

	const onSearchKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "ArrowDown") {
			e.preventDefault();
			setActiveIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
		} else if (e.key === "ArrowUp") {
			e.preventDefault();
			setActiveIndex((i) => Math.max(i - 1, 0));
		} else if (e.key === "Enter") {
			e.preventDefault();
			if (filtered[activeIndex]) pick(filtered[activeIndex]);
		} else if (e.key === "Escape") {
			setOpen(false);
		}
	};

	const triggerLabel = value ? formatModelLabel(value) : "Select model";

	return (
		<div className="model-picker" ref={rootRef}>
			<button
				type="button"
				className="model-picker-trigger"
				onClick={() => setOpen((v) => !v)}
				disabled={disabled}
				aria-haspopup="listbox"
				aria-expanded={open}
			>
				<span className="model-picker-trigger-label">{triggerLabel}</span>
				<svg
					className={`model-picker-chevron${open ? " open" : ""}`}
					viewBox="0 0 24 24"
					aria-hidden="true"
				>
					<path
						d="M6 9l6 6 6-6"
						fill="none"
						stroke="currentColor"
						strokeWidth="1.75"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
				</svg>
			</button>

			{open && (
				<div className="model-picker-menu" role="listbox" aria-label="Models">
					<div className="model-picker-search-wrap">
						<input
							ref={searchRef}
							type="search"
							className="model-picker-search"
							value={search}
							onChange={(e) => {
								setSearch(e.target.value);
								setActiveIndex(0);
							}}
							onKeyDown={onSearchKeyDown}
							placeholder="Search models"
							aria-label="Search models"
						/>
					</div>

					<ul className="model-picker-list">
						{filtered.length === 0 ? (
							<li className="model-picker-empty">No matching models</li>
						) : (
							filtered.map((m, i) => (
								<li key={m}>
									<button
										type="button"
										role="option"
										aria-selected={m === value}
										className={`model-picker-item${i === activeIndex ? " active" : ""}${
											m === value ? " selected" : ""
										}`}
										onMouseDown={(e) => {
											e.preventDefault();
											pick(m);
										}}
									>
										<span className="model-picker-item-label">
											{formatModelLabel(m)}
										</span>
										{m === value && (
											<svg
												className="model-picker-check"
												viewBox="0 0 24 24"
												aria-hidden="true"
											>
												<path
													d="M5 12l5 5L20 7"
													fill="none"
													stroke="currentColor"
													strokeWidth="2"
													strokeLinecap="round"
													strokeLinejoin="round"
												/>
											</svg>
										)}
									</button>
								</li>
							))
						)}
					</ul>

					{onReplaceKey && (
						<button
							type="button"
							className="model-picker-footer model-picker-footer-action"
							onMouseDown={(e) => {
								e.preventDefault();
								setOpen(false);
								onReplaceKey();
							}}
						>
							Replace key
						</button>
					)}
				</div>
			)}
		</div>
	);
}
