import {
	type KeyboardEvent,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";

const MAX_RESULTS = 10;
const INPUT_ID = "model-combobox-input";

type Props = {
	models: string[];
	value: string;
	onChange: (value: string) => void;
	disabled?: boolean;
};

export default function ModelCombobox({
	models,
	value,
	onChange,
	disabled,
}: Props) {
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState(value);
	const [activeIndex, setActiveIndex] = useState(0);
	const rootRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!open) setSearch(value);
	}, [value, open]);

	const filtered = useMemo(() => {
		const q = search.trim().toLowerCase();
		const list = q ? models.filter((m) => m.toLowerCase().includes(q)) : models;
		return list.slice(0, MAX_RESULTS);
	}, [models, search]);

	useEffect(() => {
		const onPointerDown = (e: MouseEvent) => {
			if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
		};
		document.addEventListener("mousedown", onPointerDown);
		return () => document.removeEventListener("mousedown", onPointerDown);
	}, []);

	const pick = (id: string) => {
		onChange(id);
		setSearch(id);
		setOpen(false);
	};

	const onBlur = () => {
		const trimmed = search.trim();
		if (trimmed) {
			onChange(trimmed);
			setSearch(trimmed);
		} else {
			setSearch(value);
		}
		setOpen(false);
	};

	const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "ArrowDown") {
			e.preventDefault();
			setOpen(true);
			setActiveIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
		} else if (e.key === "ArrowUp") {
			e.preventDefault();
			setActiveIndex((i) => Math.max(i - 1, 0));
		} else if (e.key === "Enter") {
			e.preventDefault();
			if (open && filtered[activeIndex]) {
				pick(filtered[activeIndex]);
			} else if (search.trim()) {
				pick(search.trim());
			}
		} else if (e.key === "Escape") {
			setSearch(value);
			setOpen(false);
		}
	};

	const onSearchChange = (next: string) => {
		setSearch(next);
		setActiveIndex(0);
		setOpen(true);
	};

	return (
		<div className="model-combobox" ref={rootRef}>
			<input
				id={INPUT_ID}
				type="text"
				className="model-combobox-input"
				value={search}
				onChange={(e) => onSearchChange(e.target.value)}
				onFocus={() => setOpen(true)}
				onBlur={onBlur}
				onKeyDown={onKeyDown}
				disabled={disabled}
				placeholder="Search vision + structured models…"
				role="combobox"
				aria-expanded={open}
				aria-autocomplete="list"
				aria-controls="model-combobox-list"
			/>
			{open && (
				<div
					className="model-combobox-panel"
					id="model-combobox-list"
					role="listbox"
				>
					{filtered.length === 0 ? (
						<p className="model-combobox-empty">No matching models</p>
					) : (
						filtered.map((m, i) => (
							<button
								key={m}
								type="button"
								role="option"
								aria-selected={m === value}
								className={`model-combobox-option${i === activeIndex ? " active" : ""}${
									m === value ? " selected" : ""
								}`}
								onMouseDown={(e) => {
									e.preventDefault();
									pick(m);
								}}
							>
								{m}
							</button>
						))
					)}
					{models.length > MAX_RESULTS && filtered.length === MAX_RESULTS && (
						<p className="model-combobox-hint">
							Showing top {MAX_RESULTS} matches — keep typing to narrow
						</p>
					)}
				</div>
			)}
		</div>
	);
}

export { INPUT_ID as MODEL_COMBOBOX_INPUT_ID };
