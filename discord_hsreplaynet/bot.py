#!/usr/bin/env python

import json
import subprocess

import click
import discord


@click.command()
@click.option("--config", required=True)
@click.option("-v", "--verbose", count=True)
def main(config, verbose):
	"""Synchronize HSReplay.net roles to Discord."""

	with open(config, "r") as f:
		config = json.load(f)

	intents = discord.Intents.default()
	intents.members = True
	client = discord.Client(intents=intents)

	@client.event
	async def on_error(event, *args, **kwargs):
		raise

	@client.event
	async def on_ready():
		click.echo("Logged in to Discord as %s" % (client.user.name))

		items = config["roles"]
		if not isinstance(items, list):
			items = [items]

		num_adds = 0
		num_removes = 0
		for item in items:
			guild_id = item["guild_id"]
			role_id = item["role_id"]

			click.echo("Processing role with id %s on guild with id %s" % (role_id, guild_id))

			guild = client.get_guild(guild_id)
			if guild is None:
				raise RuntimeError("Could not find guid with id %d" % guild_id)

			role = guild.get_role(role_id)
			if role is None:
				raise ValueError("Role with id %d not found on guild %r" % (role_id, guild))

			click.echo("Found %r on guild %r" % (role, guild))

			p = subprocess.Popen(
				item["command"],
				stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
			)
			output, stderr = p.communicate()
			if stderr and b"psycopg2-binary" not in stderr:
				# ignore psycopg2-binary warning (sigh)
				raise RuntimeError("Error while running command: %r" % (stderr))

			accounts = json.loads(output.decode("utf-8"))
			discord_ids = [account_data["discord_id"] for account_data in accounts]
			if verbose > 0:
				click.echo("Found %d users that should have the role" % (len(discord_ids)))

			reason_to_add = item.get("add_reason", None)
			reason_to_remove = item.get("remove_reason", None)

			# First, remove it from all members that should not have it
			role_members = list(role.members)
			for member in role_members:
				if str(member.id) in discord_ids:
					continue

				await member.remove_roles(role, reason=reason_to_remove)
				num_removes += 1
				if verbose > 0:
					click.echo("Removed role from %r" % member)

			# Then, add it to all who should
			role_member_ids = [str(member.id) for member in role_members]
			for member_id in discord_ids:
				if member_id in role_member_ids:
					continue

				member = guild.get_member(user_id=int(member_id))
				if not member:
					continue

				await member.add_roles(role, reason=reason_to_add)
				num_adds += 1
				if verbose > 0:
					click.echo("Added role to %r" % member)

			click.echo(
				"Added role to %d users and removed role from %d users" % (num_adds, num_removes)
			)

		click.echo("All roles done")
		await client.logout()

	client.run(config["token"])

if __name__ == '__main__':
	main()
