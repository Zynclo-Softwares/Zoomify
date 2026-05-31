import { useEffect, useState } from "react";
import { subscribeSchemaContactOpen } from "../schemaContact";
import SchemaContactModal from "./SchemaContactModal";

/** Global schema-service inquiry dialog (pricing, toast, settings). */
export default function SchemaContactHost() {
	const [open, setOpen] = useState(false);

	useEffect(() => subscribeSchemaContactOpen(() => setOpen(true)), []);

	return <SchemaContactModal open={open} onClose={() => setOpen(false)} />;
}
