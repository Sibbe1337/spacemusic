import { feature } from "atmn";

export const investmentMemoPdf = feature({
	internalId: "fe_3Kj8YudUiCLZV2mgu4srfnI8mXx",
	featureId: "investment_memo_pdf",
	name: "19-Slide Institutional Investment Memo PDF",
	type: "metered",
	consumable: true,
});

export const indicativeCatalogReview = feature({
	internalId: "fe_3Kj8YwEeh0UrpxvUWGCfvIkgnTO",
	featureId: "indicative_catalog_review",
	name: "Indicative Catalog Valuation & Forensics Preview",
	type: "metered",
	consumable: true,
});

export const features = [investmentMemoPdf, indicativeCatalogReview];
