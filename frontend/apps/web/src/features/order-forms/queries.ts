import { api, call, type Schemas } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export type OrderForm = Schemas["OrderFormOut"];
export type OrderFormItem = Schemas["OrderFormItemOut"];
export type DetailsType = NonNullable<OrderForm["details_type"]>;
export type AttachmentPurpose = OrderForm["attachment_purposes"][number];

/** Question sets defined in code (orders/rules.py DetailsType); the questions come in Phase 5. */
export const DETAILS_TYPES: Record<DetailsType, string> = {
  directory_listing: "E-Directory Listing",
  advertising: "Advertising",
  social_media: "Social Media Promotion",
  stand_service: "Stand Service & Contractor",
  exhibit_details: "Exhibit Details (Machinery)",
  freight: "Freight Forwarder",
  badges_visa: "Badges & Visa",
  seminar: "Seminar",
  parking: "Parking Pass",
};

export const PURPOSES: Record<AttachmentPurpose, string> = {
  LOGO: "Logo",
  PRODUCT_IMAGE: "Product Images",
  FITTING_LOCATION: "Fitting Location",
  VISA_LIST: "Visa List",
  OTHER: "Other File",
};

export const orderFormsQuery = (editionId: string) =>
  queryOptions({
    queryKey: ["order-forms", editionId, "list"],
    queryFn: () => call(api.GET("/api/v1/order-forms", { params: { query: { edition_id: editionId, page_size: 200 } } })),
  });

export const orderFormQuery = (formId: string) =>
  queryOptions({
    queryKey: ["order-forms", "form", formId],
    queryFn: () => call(api.GET("/api/v1/order-forms/{form_id}", { params: { path: { form_id: formId } } })),
  });

export const orderFormItemsQuery = (formId: string, includeInactive = true) =>
  queryOptions({
    queryKey: ["order-forms", "form", formId, "items", includeInactive],
    queryFn: () =>
      call(
        api.GET("/api/v1/order-forms/{form_id}/items", {
          params: { path: { form_id: formId }, query: { include_inactive: includeInactive, page_size: 500 } },
        }),
      ),
  });

export const itemImageUrl = (formId: string, itemId: string, version: number) =>
  `/api/v1/order-forms/${formId}/items/${itemId}/image?v=${version}`;

/** What the exhibitor fills in, for lists: "Catalog (12 items) · Questions · Attachments". */
export function formParts(f: OrderForm): string {
  const parts: string[] = [];
  if (f.has_catalog) parts.push(`Catalog (${f.active_item_count} ${f.active_item_count === 1 ? "item" : "items"})`);
  if (f.allow_custom_items) parts.push("Extra items");
  if (f.details_type) parts.push(DETAILS_TYPES[f.details_type]);
  if (f.attachment_purposes.length) parts.push(f.attachment_purposes.map((p) => PURPOSES[p]).join(", "));
  return parts.join(" · ") || "Nothing to fill yet";
}
