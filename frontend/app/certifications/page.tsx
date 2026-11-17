import type { Metadata } from "next";
import Catalog from "../../components/catalog/Catalog";

export const metadata: Metadata = {
  title: "Certifications | Edgely",
};

export default function CertificationsPage() {
  return <Catalog />;
}
