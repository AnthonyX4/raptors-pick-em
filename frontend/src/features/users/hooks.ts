import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { UserPrivate } from "@/features/auth/api"
import { meKey } from "@/features/auth/keys"
import { useAuth } from "@/features/auth/useAuth"
import { changePassword, deleteAccount, deletePicture, fetchUser, updateUser, uploadPicture, type ProfileUpdate } from "./api"
import { userKey } from "./keys"

export const useUser = (userId: number) =>
  useQuery({ queryKey: userKey(userId), queryFn: () => fetchUser(userId), enabled: Number.isInteger(userId) })

// everything a person can change about their own account. every change answers with the whole updated user,
// which goes straight into the cache the app reads "me" from
export function useAccount(user: UserPrivate) {
  const queryClient = useQueryClient()
  const { logout } = useAuth()
  const userId = user.user_id

  const keepMe = (updated: UserPrivate) => queryClient.setQueryData(meKey, updated)

  // a new name or picture is shown on messages, picks and standings that are already cached
  const refreshShown = () => queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== meKey[0] })

  return {
    update: useMutation({
      mutationFn: (body: ProfileUpdate) => updateUser(userId, body),
      onSuccess: (updated, body) => {
        keepMe(updated)
        if (body.username !== undefined) void refreshShown()
      },
    }),
    changePassword: useMutation({
      mutationFn: ({ currentPassword, newPassword }: { currentPassword: string; newPassword: string }) =>
        changePassword(currentPassword, newPassword),
    }),
    uploadPicture: useMutation({
      mutationFn: (file: File) => uploadPicture(userId, file),
      onSuccess: (updated) => {
        keepMe(updated)
        void refreshShown()
      },
    }),
    removePicture: useMutation({
      mutationFn: () => deletePicture(userId),
      onSuccess: (updated) => {
        keepMe(updated)
        void refreshShown()
      },
    }),
    // the account is gone, so the session ends here: logging out clears the token and the whole cache
    deleteAccount: useMutation({
      mutationFn: () => deleteAccount(userId),
      onSuccess: () => logout(),
    }),
  }
}
