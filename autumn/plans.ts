import { plan } from "atmn";
import { indicativeCatalogReview, investmentMemoPdf } from "./features";

export const freePreview = plan({
	internalId: "prod_3Kj8YtTScIWFnIbLzSFXjoJPG2m",
	planId: "free_preview",
	name: "Free Catalog Review & Preview",
	description:
		"Free indicative Monte Carlo DCF & DTW catalog review with Slides 01–02 memo preview",
	autoEnable: true,
	active: true,
	versionSlug: "v1",
	items: [
		{
			featureId: indicativeCatalogReview.featureId,
			included: 3,
			reset: {
				interval: "month",
			},
		},
	],
});

export const deskPass499 = plan({
	internalId: "prod_3Kj8YuySKeTNKG0yQYB7rviYpQF",
	planId: "desk_pass_499",
	name: "SPACE Manager / Label Underwriting Desk Pass",
	description:
		"Up to 10 institutional 19-slide 16:9 catalog investment memos per month plus unlimited indicative reviews",
	active: true,
	versionSlug: "v1",
	price: {
		amount: 499,
		interval: "month",
	},
	items: [
		{
			featureId: investmentMemoPdf.featureId,
			included: 10,
			reset: {
				interval: "month",
			},
		},
		{
			featureId: indicativeCatalogReview.featureId,
			unlimited: true,
		},
	],
});

export const singleMemo299 = plan({
	internalId: "prod_3Kj8YraIPtdN3uwgvgBZmRxsX0G",
	planId: "single_memo_299",
	name: "SPACE 19-Slide Institutional Investment Memo",
	description:
		"One-off 19-slide 16:9 institutional catalog valuation memo PDF + 10Y DCF schedule",
	addOn: true,
	active: true,
	versionSlug: "v1",
	price: {
		amount: 299,
		interval: "one_off",
	},
	items: [
		{
			featureId: investmentMemoPdf.featureId,
			included: 1,
		},
	],
});

export const plans = [freePreview, deskPass499, singleMemo299];
