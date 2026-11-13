import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import type { LoadedModel } from "./TeacherPreview";

export const MAX_AVATAR_BYTES = 25 * 1024 * 1024;

export function validateAvatarFile(file: Pick<File, "name" | "size">): void {
  if (!file.name.toLowerCase().endsWith(".glb")) throw new Error("Choose a single-file .glb avatar.");
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

export async function loadLocalAvatar(file: File): Promise<LoadedModel> {
  validateAvatarFile(file);
  const buffer = await file.arrayBuffer();
  const model = await new Promise<LoadedModel>((resolve, reject) => {
    new GLTFLoader().parse(buffer, "", gltf => resolve({ scene: gltf.scene, clips: gltf.animations }), reject);
  });
  if (!hasRiggedCharacter(model)) {
    disposeAvatar(model);
    throw new Error("This GLB has no rigged character. Choose a licensed, skinned human avatar.");
  }
  return model;
}
