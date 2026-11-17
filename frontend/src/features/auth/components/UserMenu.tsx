import { ChevronDown } from "lucide-react"
import { Link } from "react-router"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { UserPrivate } from "../api"
import { useAuth } from "../useAuth"

export function UserMenu({ user }: { user: UserPrivate }) {
  const { logout } = useAuth()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-md text-sm font-bold tracking-wide text-white/80 uppercase transition-colors outline-none hover:text-white focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:text-white">
        <Avatar className="size-8">
          <AvatarImage src={user.image_path} alt="" />
          <AvatarFallback>{user.username.slice(0, 1).toUpperCase()}</AvatarFallback>
        </Avatar>
        <span className="max-w-32 truncate max-md:hidden">{user.username}</span>
        <ChevronDown className="size-4" aria-hidden />
        <span className="sr-only">Account menu</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel className="truncate">{user.username}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to={`/users/${user.user_id}`}>My profile</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/settings">Settings</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout}>Log out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
