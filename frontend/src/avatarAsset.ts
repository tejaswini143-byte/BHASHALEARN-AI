import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, type VRM } from "@pixiv/three-vrm";
import type { LoadedModel } from "./TeacherPreview";

export const MAX_AVATAR_BYTES = 25 * 1024 * 1024;

export function validateAvatarFile(file: Pick<File, "name" | "size">): void {
  if (!/\.(glb|vrm)$/i.test(file.name)) throw new Error("Choose a single-file .glb or .vrm avatar.");
  if (file.size <= 0) throw new Error("The avatar file is empty.");
  if (file.size > MAX_AVATAR_BYTES) throw new Error("Avatar exceeds the 25 MB local upload limit.");
}

export function hasRiggedCharacter(model: LoadedModel): boolean {
  let rigged = false;
  model.scene.traverse(node => { if ((node as THREE.SkinnedMesh).isSkinnedMesh) rigged = true; });
  return rigged;
}

export function disposeAvatar(model: LoadedModel): void {
  const textures = new Set<THREE.Texture>();
  const materials = new Set<THREE.Material>();
  const geometries = new Set<THREE.BufferGeometry>();
  model.scene.traverse(node => {
    const mesh = node as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry);
    for (const material of Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : []) {
      materials.add(material);
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
    }
  });
  textures.forEach(texture => texture.dispose());
  materials.forEach(material => material.dispose());
  geometries.forEach(geometry => geometry.dispose());
}

export async function loadAvatarBuffer(buffer: ArrayBuffer, filename: string): Promise<LoadedModel> {
  const loader = new GLTFLoader();
  const isVrm = filename.toLowerCase().endsWith(".vrm");
  if (isVrm) loader.register(parser => new VRMLoaderPlugin(parser));
  const model = await new Promise<LoadedModel>((resolve, reject) => {
    loader.parse(buffer, "", gltf => {
      const vrm = gltf.userData.vrm as VRM | undefined;
      resolve({ scene: vrm?.scene ?? gltf.scene, clips: gltf.animations, vrm });
    }, reject);
  });
  if (!hasRiggedCharacter(model)) {
    disposeAvatar(model);
    throw new Error("This avatar has no rigged character. Choose a licensed, skinned human avatar.");
  }
  return model;
}

export async function loadLocalAvatar(file: File): Promise<LoadedModel> {
  validateAvatarFile(file);
  return loadAvatarBuffer(await file.arrayBuffer(), file.name);
}

export async function loadBundledAvatar(): Promise<LoadedModel> {
  const response = await fetch("/avatars/AvatarSample_B.vrm");
  if (!response.ok) throw new Error(`Bundled teacher avatar could not load (HTTP ${response.status}).`);
  const buffer = await response.arrayBuffer();
  if (buffer.byteLength > MAX_AVATAR_BYTES) throw new Error("Bundled teacher avatar exceeds the 25 MB loading limit.");
  return loadAvatarBuffer(buffer, "AvatarSample_B.vrm");
}
