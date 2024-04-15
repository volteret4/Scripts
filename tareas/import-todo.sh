#!/usr/bin/env bash
#
# Script Name: import-todo.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#
##############################################################################
##
## Copyright 2006 - 2017, Paul Beckingham, Federico Hernandez.
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included
## in all copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
## OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
## THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.
##
## http://www.opensource.org/licenses/mit-license.php
##
################################################################################

use strict;
use warnings;
use Time::Local;

# Priority mappings.
my %priority_map = (
  'a' => 'H', 'b' => 'M', 'c' => 'L', 'd' => 'L', 'e' => 'L', 'f' => 'L',
  'g' => 'L', 'h' => 'L', 'i' => 'L', 'j' => 'L', 'k' => 'L', 'l' => 'L',
  'm' => 'L', 'n' => 'L', 'o' => 'L', 'p' => 'L', 'q' => 'L', 'r' => 'L',
  's' => 'L', 't' => 'L', 'u' => 'L', 'v' => 'L', 'w' => 'L', 'x' => 'L',
  'y' => 'L', 'z' => 'L');

my @tasks;
while (my $todo = <>)
{
  my $status = 'pending';
  my $priority = '';
  my $entry = '';
  my $end = '';
  my @projects;
  my @contexts;
  my $description = '';
  my $due = '';

  # pending + pri + entry
  if ($todo =~ /^\(([A-Z])\)\s(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $priority, $entry, $description) = ('pending', $1, epoch ($2), $3);
  }

  # pending + pri
  elsif ($todo =~ /^\(([A-Z])\)\s(.+)$/i)
  {
    ($status, $priority, $description) = ('pending', $1, $2);
  }

  # pending + entry
  elsif ($todo =~ /^(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $entry, $description) = ('pending', epoch ($1), $2);
  }

  # done + end + entry
  elsif ($todo =~ /^x\s(\d{4}-\d{2}-\d{2})\s(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $end, $entry, $description) = ('completed', epoch ($1), epoch ($2), $3);
  }

  # done + end
  elsif ($todo =~ /^x\s(\d{4}-\d{2}-\d{2})\s(.+)$/i)
  {
    ($status, $end, $description) = ('completed', epoch ($1), $2);
  }

  # done
  elsif ($todo =~ /^x\s(.+)$/i)
  {
    ($status, $description) = ('completed', $1);
  }

  # pending
  elsif ($todo =~ /^(.+)$/i)
  {
    ($status, $description) = ('pending', $1);
  }

  # Project
  @projects = $description =~ /\+(\S+)/ig;

  # Contexts
  @contexts = $description =~ /\@(\S+)/ig;

  # Due
  $due = epoch ($1) if $todo =~ /\sdue:(\d{4}-\d{2}-\d{2})/i;

  # Map priorities
  $priority = $priority_map{lc $priority} if $priority ne '';

  # Pick first project
  my $first_project = shift @projects;

  # Compose the JSON
  my $json = '';
  $json .= "{\"status\":\"${status}\"";
  $json .= ",\"priority\":\"${priority}\""     if defined $priority && $priority ne '';
  $json .= ",\"project\":\"${first_project}\"" if defined $first_project && $first_project ne '';
  $json .= ",\"entry\":\"${entry}\""           if $entry ne '';
  $json .= ",\"end\":\"${end}\""               if $end ne '';
  $json .= ",\"due\":\"${due}\""               if $due ne '';

  if (@contexts)
  {
    $json .= ",\"tags\":[" . join (',', map {"\"$_\""} @contexts) . "]";
  }

  $json .= ",\"description\":\"${description}\"}";

  push @tasks, $json;
}

print "[\n", join ("\n", @tasks), "\n]\n";
exit 0;

################################################################################
sub epoch
{
  my ($input) = @_;

  my ($y, $m, $d) = $input =~ /(\d{4})-(\d{2})-(\d{2})/;
  return timelocal (0, 0, 0, $d, $m-1, $y-1900);
}

################################################################################

__DATA__
https://www.youtube.com/watch?v=G_yLtN7n4Vo +deep
https://www.youtube.com/watch?v=CPnyKzHmvws +jazz
2022-06-05 https://www.youtube.com/watch?v=jXFPwDo5AA8 +deep
2022-06-05 https://www.youtube.com/watch?v=CPnyKzHmvws +jazz
2022-06-05 https://www.youtube.com/watch?v=Uta02hfUF4o +ambient
2022-06-05 https://www.youtube.com/watch?v=Uta02hfUF4o +jazz
(B) 2022-06-05 https://thekyotoconnectionioj.bandcamp.com/album/the-flower-the-bird-and-the-mountain +ambient
2022-06-05 https://www.youtube.com/watch?v=4J9E6Q5VTIA +deep
(C) 2022-06-05 https://www.youtube.com/watch?v=3KCbqhJt16k +rock +psicodelia
2022-06-05 https://www.youtube.com/watch?v=ul3e2-ExhF0 +deep +mix?
2022-06-06 https://www.youtube.com/watch?v=-9RvqnHc-Wg +deep +house
2022-06-06 https://www.youtube.com/watch?v=02ZhH8_IMcI +ambient +awakenings
2022-06-06 https://www.youtube.com/watch?v=TxtFR20NV8Q +disco +egipto +banbantonton
2022-06-06 https://www.youtube.com/watch?v=teGONNABXNc +ambient
2022-06-06 https://orpheus.network/index.php +ambient
2022-06-07 https://www.soundohm.com/product/paradia-lp +ambient
2022-06-07 https://www.soundohm.com/product/soul-impressions +funk +soul
2022-06-07 Island music from memory, ebalunga!!!@malamusica
2022-06-07 https://www.youtube.com/watch?v=1teSrZ1LE7M +ambient
2022-06-07 https://moltobrutto.bandcamp.com/album/album +deep
(A) 2022-06-07 https://www.beatport.com/release/scruffy-soul-006/3712874 +deep +musthave
2022-06-07 https://chipwickham.bandcamp.com/album/astral-traveling +jazz +ambient
2022-06-07 https://hobbesmusicon.bandcamp.com/album/pay-it-forward-lp-hm017lp-disco-house-ambient-balearic +disco +deep
2022-06-07 https://coastlines-music.bandcamp.com/album/coastlines-2-2 +deep +musthave
2022-06-07 https://coastlines-music.bandcamp.com/album/coastlines +deep +musthave
2022-06-07 https://projectgemini.bandcamp.com/album/the-children-of-scorpio +jazz +deep +psicodelia
2022-06-07 https://www.youtube.com/watch?v=yn-yFWd3zRE +deep +chillout +mix?
2022-06-08 https://panamerican.bandcamp.com/album/the-patience-fader +ambient
2022-06-08 https://www.youtube.com/watch?v=Si2mi2m1-VY&t=281s +deep
2022-06-08 https://www.youtube.com/watch?v=P8bdrQXq-gM&t=128s +ambient +keet
2022-06-08 https://banbantonton.com/2022/04/30/klaus-schulze-4-august-1947-26-april-2022/ +ambient +banbantonton +discografía
2022-06-08 https://www.youtube.com/watch?v=7cWtVuD3nKw +mix? +ambient +keet
2022-06-08 https://www.youtube.com/watch?v=xB7ujid9wUg +ambient
2022-06-08 https://www.youtube.com/watch?v=fcojnZTwR3s +awakenings
2022-06-08 .132:19999. +deep
2022-06-08 +deep +chillout +ambient
2022-06-08 https://www.youtube.com/watch?v=f5va6LoK_94&t=195s +deep +mix?
2022-06-09 https://banbantonton.com/2022/04/24/balearic-mikes-musical-diets-week-43-the-klf/ +discografia +klf +ambient
2022-06-09 https://analogafrica.bandcamp.com/album/orchestre-massako-limited-dance-edition +africa +afrobeat
2022-06-09 https://cantomamusic.bandcamp.com/album/alive-ft-quinn-lamont-luke-conrad-mcdonnell-remixes-2 +deep
2022-06-11 A Strangely Isolated Place +malamusica +sello +ambient +eeuu
2022-06-11 https://mynunorthernsoul.bandcamp.com/album/summer-selection-four +deep
2022-06-11 https://www.youtube.com/watch?v=jG4nXXMWIPI +jazz
2022-06-11 https://luridmusic.bandcamp.com/album/may-that-war-be-cursed-vol-1 +ambient +keet +psicodelia
2022-06-11 https://www.youtube.com/watch?v=piF-ObPhQPc +ambient +deep +chillout
2022-06-12 +ambient +psicodelia +keet
